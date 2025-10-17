import argparse
import dataclasses
import datetime
import logging
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable, Sequence
from decimal import Decimal
from io import BytesIO
from types import TracebackType
from typing import BinaryIO, ClassVar, Self, override

import niquests
import xlrd

from . import bonds

# The upside is that this is a JSON API, the downside is that data for the month
# is published after it starts, while the bonds have already been announced before.
# Data on https://www.gov.pl/web/finanse/obligacje-detaliczne1 does not have this delay.
DATASET_RESOURCES_URL = "https://api.dane.gov.pl/1.4/datasets/805/resources"

log = logging.getLogger()


@dataclasses.dataclass(kw_only=True)
class ExecutionParams:
    download_dataset: bool = True


class BondExtractor(ABC):
    HEADER_ROW_COUNT: ClassVar = 2
    START_DATE: ClassVar = datetime.date(2003, 8, 1)
    TYPE_NAME: ClassVar[str]
    INTEREST_RATE_COUNT: ClassVar[int]

    def __init__(self, book: xlrd.Book) -> None:
        self._book = book
        self._sheet = book.sheet_by_name(self.TYPE_NAME)
        self._row_names = [cell.value for cell in self._sheet[0]]

    def get_interest_rates(self, row: list[xlrd.sheet.Cell]) -> Sequence[Decimal]:
        apr_col_idx = self._row_names.index("Oprocentowanie")
        return [
            Decimal(str(cell.value))
            for period_idx in range(self.INTEREST_RATE_COUNT)
            if (cell := row[apr_col_idx + period_idx]).ctype
        ]

    @staticmethod
    @abstractmethod
    def create_bond(
        *,
        series_name: str,
        isin: str,
        sale_from: datetime.date,
        sale_to: datetime.date,
        interest_rate: Iterable[Decimal],
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
            )
            bonds.append(bond)

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
    ) -> bonds.Bond:
        return bonds.create_tos_bond(
            series_name=series_name,
            isin=isin,
            sale_from=sale_from,
            sale_to=sale_to,
            interest_rate=next(iter(interest_rate)),
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
        args = parser.parse_args()
        if args.bonds_dataset is not None:
            self._bonds_dataset_file = open(args.bonds_dataset, "rb")  # noqa: SIM115
            self.execution_params.download_dataset = False

    def run(self) -> int:
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S",
            level=logging.INFO,
        )
        self._parse_args()

        if self.execution_params.download_dataset:
            self.download_bonds_dataset()

        self.parse_bonds_dataset()

        return 0

    def download_bonds_dataset(self) -> None:
        resources_resp = self._session.get(DATASET_RESOURCES_URL)
        resources = resources_resp.raise_for_status().json()["data"]
        if len(resources) != 1:
            raise RuntimeError("unexpected number of resources in the dataset")
        download_url = resources[0]["attributes"]["download_url"]
        log.info("Downloading dataset resource at %s...", download_url)
        file_resp = self._session.get(download_url)
        content = file_resp.content
        if content is None:
            raise RuntimeError("file_resp.content is None")
        self._bonds_dataset_file = BytesIO(content)

    def parse_bonds_dataset(self) -> None:
        book = xlrd.open_workbook(file_contents=self._bonds_dataset_file.read())

        bonds: dict[str, list[bonds.Bond]] = {}

        for extractor_cls in EXTRACTORS:
            extractor = extractor_cls(book)
            print("Extracting", extractor.TYPE_NAME, "bonds...")
            bonds[extractor.TYPE_NAME] = extractor.extract_bonds()


def main() -> None:
    with App() as app:
        raise SystemExit(app.run())


if __name__ == "__main__":
    main()
