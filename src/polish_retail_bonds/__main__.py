import argparse
import dataclasses
import datetime
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Iterable, Sequence
from decimal import Decimal
from functools import cached_property
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, ClassVar, Self, override
from urllib.parse import urljoin

import niquests
import orjson
import pypdfium2 as pdfium
import xlrd
from lxml import etree

from . import bonds

# The downside is that this is extracted from HTML and there's no API
# but the upside is that it's not delayed like the data exposed through
# https://api.dane.gov.pl/1.4/datasets/805/resources
DATASET_SOURCE_URL = "https://www.gov.pl/web/finanse/obligacje-detaliczne1"
DATASET_SOURCE_XPATH = (
    ".//a["
    " contains(@class, 'file-download')"
    " and contains(@aria-label, 'Dane_dotyczace_obligacji_detalicznych.xls')"
    "]/@href"
)
BOND_PDF_API_URL = "https://www.finanse.mf.gov.pl/dlug-publiczny/bony-i-obligacje-hurtowe/wyszukiwarka-listow-emisyjnych"
# "nwarosłych" is a typo found in one of the PDFs
EARLY_REDEMPTION_COST_RE = re.compile(
    r"("
    r"nale.no..\s+wyp.acona\s+z\s+tytu.u\s+przedterminowego\s+wykupu\s+jednej\s+"
    r"obligacji\s+jest\s+pomniejszana\s+o\s+kwot.\s+nw?arosłych\s+odsetek,\s+"
    r"ale\s+nie\s+wy.sz.\s+ni."
    r"|"
    r"nale.no..\s+wyp.acona\s+z\s+tytu.u\s+przedterminowego\s+wykupu\s+jednej\s+"
    r"obligacji\s+jest\s+pomniejszana\s+o\s+kwot.\s+"
    r"|"
    r"przy\s+wyp.acie\s+.wiadcze.\s+z\s+tytu.u\s+przedterminowego\s+wykupu,\s+"
    r"wysoko..\s+odsetek\s+nale.nych\s+od\s+ka.dej\s+obligacji\s+jest\s+pomniejszana\s+"
    r"o\s+kwot."
    r"|"
    r"przy\s+wyp.acie\s+.wiadcze.\s+z\s+tytu.u\s+przedterminowego\s+wykupu,\s+"
    r"wysoko..\s+odsetek\s+nale.nych\s+od\s+ka.dej\s+obligacji\s+pomniejszana\s+jest\s+"
    r"o\s+kwot."
    r"|"
    r"przy\s+wyp.acie\s+.wiadcze.\s+z\s+tytu.u\s+przedterminowego\s+wykupu,\s+"
    r"wysoko..\s+nale.no.ci\s+od\s+ka.dej\s+obligacji\s+jest\s+pomniejszana\s+"
    r"o\s+kwot."
    r")"
    r"\s+(\d+(,\d+)?)\s+z."
)
MIN_SELL_VALUE_AT_NOMINAL_RE = re.compile(
    r"("
    r"nale.no..\s+wyp.acona\s+z\s+tytu.u\s+przedterminowego\s+wykupu\s+jednej\s+"
    r"obligacji\s+jest\s+pomniejszana\s+o\s+kwot.\s+nw?arosłych\s+odsetek,\s+"
    r"ale\s+nie\s+wy.sz.\s+ni."
    r"|"
    r"nale.no..\s+wyp.acona\s+z\s+tytu.u\s+przedterminowego\s+wykupu\s+jednej\s+"
    r"obligacji\s+nie\s+mo.e\s+by.\s+ni.sza\s+od\s+warto.ci\s+nominalnej\s+"
    r"obligacji\."
    r"|"
    r"z\s+zastrze.eniem,\s+.e\s+nie\s+mo.e\s+by.\s+ni.sza\s+od\s+warto.ci\s+"
    r"nominalnej\s+obligacji"
    r")"
)

log = logging.getLogger()


@dataclasses.dataclass(kw_only=True)
class ExecutionParams:
    download_dataset: bool = True


class Pdf:
    def __init__(self, path: Path) -> None:
        self._pdf_doc = pdfium.PdfDocument(path)

    @cached_property
    def content(self) -> str:
        pages: list[str] = []
        for page in self._pdf_doc:
            textpage = page.get_textpage()
            pages.append(textpage.get_text_bounded())
        return "\n".join(pages)


class BondExtractor(ABC):
    HEADER_ROW_COUNT: ClassVar = 2
    START_DATE: ClassVar = datetime.date(2003, 8, 1)
    TYPE_NAME: ClassVar[str]
    INTEREST_RATE_COUNT: ClassVar[int]

    def __init__(
        self, book: xlrd.Book, get_bond_pdf_func: Callable[[str, str], Pdf]
    ) -> None:
        self._book = book
        self._get_bond_pdf_func = get_bond_pdf_func
        self._sheet = book.sheet_by_name(self.TYPE_NAME)
        self._row_names = [cell.value for cell in self._sheet[0]]

    def get_interest_rates(self, row: list[xlrd.sheet.Cell]) -> Sequence[Decimal]:
        apr_col_idx = self._row_names.index("Oprocentowanie")
        return [
            Decimal(str(round(float(cell.value), 4)))
            for period_idx in range(self.INTEREST_RATE_COUNT)
            if (cell := row[apr_col_idx + period_idx]).ctype
        ]

    def ensure_min_sell_value_at_nominal(self, series_name: str, isin: str) -> None:
        pdf = self._get_bond_pdf_func(series_name, isin)
        match = MIN_SELL_VALUE_AT_NOMINAL_RE.search(pdf.content)
        if match is None:
            raise RuntimeError(
                f"could not find 'minimum sell value at nominal' clause for {isin}"
            )

    def get_early_redemption_cost(self, series_name: str, isin: str) -> Decimal:
        pdf = self._get_bond_pdf_func(series_name, isin)
        match = EARLY_REDEMPTION_COST_RE.search(pdf.content)
        if match is None:
            raise RuntimeError(f"could not find early redemption cost for {isin}")
        return Decimal(match.group(2).replace(",", "."))

    @staticmethod
    @abstractmethod
    def create_bond(
        *,
        series_name: str,
        isin: str,
        sale_from: datetime.date,
        sale_to: datetime.date,
        interest_rate: Iterable[Decimal],
        early_redemption_cost: Decimal,
    ) -> bonds.Bond:
        raise NotImplementedError

    def extract_bonds(self) -> list[bonds.Bond]:
        series_col_idx = self._row_names.index("Seria")
        isin_col_idx = self._row_names.index("Kod ISIN")
        start_col_idx = self._row_names.index("Pocz\u0105tek sprzeda\u017cy")
        end_col_idx = self._row_names.index("Koniec sprzeda\u017cy")

        rows: Generator[list[xlrd.sheet.Cell]] = self._sheet.get_rows()  # pyright: ignore[reportAssignmentType]
        # skip multi-row headers
        for _ in range(self.HEADER_ROW_COUNT):
            next(rows)

        bonds: list[bonds.Bond] = []
        for row in rows:
            start_value = row[start_col_idx].value
            assert isinstance(start_value, float)
            sale_from = xlrd.xldate_as_datetime(start_value, 0).date()
            if sale_from < self.START_DATE:
                continue

            end_value = row[end_col_idx].value
            assert isinstance(end_value, float)
            sale_to = xlrd.xldate_as_datetime(end_value, 0).date()

            series_name = row[series_col_idx].value.strip()
            isin = row[isin_col_idx].value.strip()
            bond = self.create_bond(
                series_name=series_name,
                isin=isin,
                sale_from=sale_from,
                sale_to=sale_to,
                interest_rate=self.get_interest_rates(row),
                early_redemption_cost=self.get_early_redemption_cost(series_name, isin),
            )
            bonds.append(bond)
            self.ensure_min_sell_value_at_nominal(series_name, isin)

        return bonds


class RORBondExtractor(BondExtractor):
    TYPE_NAME = "ROR"
    INTEREST_RATE_COUNT = 12
    create_bond = staticmethod(bonds.create_ror_bond)


class DORBondExtractor(BondExtractor):
    TYPE_NAME = "DOR"
    INTEREST_RATE_COUNT = 24
    create_bond = staticmethod(bonds.create_dor_bond)


class TOSBondExtractor(BondExtractor):
    TYPE_NAME = "TOS"
    INTEREST_RATE_COUNT = 1

    @override
    @staticmethod
    def create_bond(
        *,
        series_name: str,
        isin: str,
        sale_from: datetime.date,
        sale_to: datetime.date,
        interest_rate: Iterable[Decimal],
        early_redemption_cost: Decimal,
    ) -> bonds.Bond:
        return bonds.create_tos_bond(
            series_name=series_name,
            isin=isin,
            sale_from=sale_from,
            sale_to=sale_to,
            interest_rate=next(iter(interest_rate)),
            early_redemption_cost=early_redemption_cost,
        )


class COIBondExtractor(BondExtractor):
    TYPE_NAME = "COI"
    INTEREST_RATE_COUNT = 4
    create_bond = staticmethod(bonds.create_coi_bond)


class EDOBondExtractor(BondExtractor):
    TYPE_NAME = "EDO"
    INTEREST_RATE_COUNT = 10
    create_bond = staticmethod(bonds.create_edo_bond)


class ROSBondExtractor(BondExtractor):
    TYPE_NAME = "ROS"
    INTEREST_RATE_COUNT = 6
    create_bond = staticmethod(bonds.create_ros_bond)


class RODBondExtractor(BondExtractor):
    TYPE_NAME = "ROD"
    INTEREST_RATE_COUNT = 12
    create_bond = staticmethod(bonds.create_rod_bond)


EXTRACTORS = (
    RORBondExtractor,
    DORBondExtractor,
    TOSBondExtractor,
    COIBondExtractor,
    EDOBondExtractor,
    ROSBondExtractor,
    RODBondExtractor,
)


class App:
    def __init__(self) -> None:
        self._session = niquests.Session()
        self._closed = False
        self._bonds_dataset_file: BinaryIO = BytesIO()
        self._bond_pdf_cache_dir = Path()
        self._file_tree_output = Path()
        self.execution_params = ExecutionParams()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._session.close()
        self._bonds_dataset_file.close()

    def _parse_args(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--bonds-dataset",
            help=(
                "Path to the bonds dataset in XLS format."
                " If not specified, the dataset will be downloaded for the current run."
            ),
        )
        parser.add_argument(
            "--bond-pdf-cache",
            help="Path to the cache of bond PDF files.",
            required=True,
        )
        parser.add_argument(
            "--file-tree",
            help="Path to the directory that the file tree should be output to.",
            required=True,
        )
        args = parser.parse_args()
        if args.bonds_dataset is not None:
            self._bonds_dataset_file = open(args.bonds_dataset, "rb")  # noqa: SIM115
            self.execution_params.download_dataset = False
        self._bond_pdf_cache_dir = Path(args.bond_pdf_cache)
        self._bond_pdf_cache_dir.mkdir(exist_ok=True)
        self._file_tree_output = Path(args.file_tree)
        self._file_tree_output.mkdir(exist_ok=True)

    def run(self) -> int:
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S",
            level=logging.INFO,
        )
        self._parse_args()

        if self.execution_params.download_dataset:
            self.download_bonds_dataset()

        bonds = self.parse_bonds_dataset()
        self.generate_file_tree(bonds)

        return 0

    def get_bond_pdf(self, series_name: str, isin: str) -> Pdf:
        path = self._bond_pdf_cache_dir / f"{isin}.pdf"
        try:
            pdf = Pdf(path)
        except FileNotFoundError:
            pass
        else:
            return pdf

        params = {
            "p_p_id": "securityissueviewportlet_WAR_mfportalsecuritiestradingportlet",
            "p_p_lifecycle": "2",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "p_p_cacheability": "cacheLevelPage",
            "p_p_col_id": "column-1",
            "p_p_col_pos": "1",
            "p_p_col_count": "2",
        }
        for data in (f"GET_ISSUES\n\n\n{isin}\n", f"GET_ISSUES\n\n{series_name}\n\n"):
            resp = self._session.post(
                BOND_PDF_API_URL,
                params=params,
                headers={"Content-Type": "application/json; charset=utf-8"},
                data=data,
            ).raise_for_status()
            try:
                bond_data = resp.json()[0]
            except IndexError:
                print(f"no bond_data for isin {isin}")
            else:
                break
        else:
            raise RuntimeError(
                f"no bond_data for isin {isin} and series name {series_name}"
            )
        if (
            bond_data["isin"].strip() != isin
            and bond_data["series"].strip() != series_name
        ):
            raise RuntimeError(f"unexpected bond_data for isin {isin}: {bond_data}")
        files = [
            filename
            for filename in bond_data["letters"]
            if "aneks" not in filename.lower()
        ]
        if len(files) != 1:
            raise RuntimeError(
                f"unexpected number of files in bond_data for isin {isin}: {bond_data}"
            )

        resp = self._session.get(
            BOND_PDF_API_URL, params={**params, "fileName": files[0]}
        ).raise_for_status()
        with open(path, "wb") as fp:
            fp.writelines(resp.iter_content(chunk_size=128))

        return Pdf(path)

    def download_bonds_dataset(self) -> None:
        source_resp = self._session.get(DATASET_SOURCE_URL).raise_for_status()
        root = etree.HTML(source_resp.content)
        links = root.xpath(DATASET_SOURCE_XPATH)
        if len(links) != 1:
            raise RuntimeError(
                "unexpected number of matching links in the dataset source"
            )
        download_url = urljoin(DATASET_SOURCE_URL, links[0])
        log.info("Downloading dataset resource at %s...", download_url)
        file_resp = self._session.get(download_url)
        content = file_resp.content
        if content is None:
            raise RuntimeError("file_resp.content is None")
        self._bonds_dataset_file = BytesIO(content)

    def parse_bonds_dataset(self) -> list[bonds.Bond]:
        book = xlrd.open_workbook(file_contents=self._bonds_dataset_file.read())

        bonds: list[bonds.Bond] = []

        for extractor_cls in EXTRACTORS:
            extractor = extractor_cls(book, self.get_bond_pdf)
            print("Extracting", extractor.TYPE_NAME, "bonds...")
            bonds.extend(extractor.extract_bonds())

        return bonds

    def generate_file_tree(self, bonds: list[bonds.Bond]) -> None:
        base_dir = self._file_tree_output
        for bond in bonds:
            month_dir = base_dir / bond.sale_to.strftime("%Y/%m")
            metadata_path = month_dir / f"{bond.series_name}_metadata.json"
            new_metadata = bond.to_json_dict()
            try:
                with open(metadata_path, "rb") as fp:
                    old_metadata = orjson.loads(fp.read())
            except FileNotFoundError:
                pass
            else:
                if old_metadata == new_metadata:
                    print("No changes found for bond", bond.series_name)
                    continue

            month_dir.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "wb") as fp:
                fp.write(orjson.dumps(new_metadata))

            for day_idx in range((bond.sale_to - bond.sale_from).days + 1):
                offset = datetime.timedelta(days=day_idx)
                day = bond.sale_from + offset
                day_dir = base_dir / day.strftime("%Y/%m/%d")
                day_dir.mkdir(parents=True, exist_ok=True)
                data = [
                    {"d": (date + offset).isoformat(), "v": str(value)}
                    for date, value in bond.total_redemption_values.iter_with_dates()
                ]
                with open(
                    day_dir / f"{bond.series_name}_total_redemption_values.json", "wb"
                ) as fp:
                    fp.write(orjson.dumps(data))


def main() -> None:
    with App() as app:
        raise SystemExit(app.run())


if __name__ == "__main__":
    main()
