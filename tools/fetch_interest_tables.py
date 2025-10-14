#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.14"
# dependencies = ["niquests>=3.15.2"]
# ///

import argparse
import calendar
import dataclasses
import datetime
import io
from decimal import Decimal
from operator import itemgetter
from pathlib import Path

import niquests

BASE_API_URL = "https://www.pekao.com.pl/.rest/gb-interest-tables/emissions"
START_DATE = datetime.date(2022, 10, 1)
END_DATE = datetime.date.today().replace(day=1)
ROMAN_NUMERALS = (
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
)
POLISH_DATE_FORMAT = "%d.%m.%Y"


@dataclasses.dataclass
class BondParameters:
    period_count: int
    is_yearly: bool
    has_compound_interest: bool


BOND_TYPES = {
    "ROR": BondParameters(1 * 12, is_yearly=False, has_compound_interest=False),
    "DOR": BondParameters(2 * 12, is_yearly=False, has_compound_interest=False),
    "TOS": BondParameters(3, is_yearly=True, has_compound_interest=True),
    "COI": BondParameters(4, is_yearly=True, has_compound_interest=False),
    "EDO": BondParameters(10, is_yearly=True, has_compound_interest=True),
    # family bonds are not available at Pekao
    # "ROS": BondParameters(6, is_yearly=True, has_compound_interest=True),
    # "ROD": BondParameters(12, is_yearly=True, has_compound_interest=True),
}


def add_months(date: datetime.date, month_count: int) -> datetime.date:
    year, month = divmod(date.month + month_count - 1, 12)
    year += date.year
    month += 1
    _, max_day = calendar.monthrange(year, month)
    return date.replace(year=year, month=month, day=min(date.day, max_day))


def fetch_bond_interest_tables(
    bond_type: str,
    bond_params: BondParameters,
    *,
    start_date: datetime.date = START_DATE,
    file: io.Writer[str] | None = None,
) -> None:
    period_count = bond_params.period_count
    sale_from = start_date
    while sale_from <= END_DATE:
        sale_to = sale_from.replace(
            day=calendar.monthrange(sale_from.year, sale_from.month)[1]
        )
        redemption_date = add_months(
            sale_from,
            12 * period_count if bond_params.is_yearly else period_count,
        )
        series = bond_type + redemption_date.strftime("%m%y")
        series_url = f"{BASE_API_URL}/{series}"
        resp = niquests.get(series_url).raise_for_status()
        periods = resp.json()

        period_symbol = "Y" if bond_params.is_yearly else "M"
        interest_symbol = "C" if bond_params.has_compound_interest else "S"
        print(
            f"{series};{sale_from};{sale_to};{redemption_date};"
            f"{period_symbol};{period_count};{interest_symbol}",
            file=file,
        )
        for period in range(1, period_count + 1):
            period_name = f"{period}-1"
            if period_name not in periods:
                print(file=file)
                continue
            resp = niquests.get(f"{series_url}/{period_name}").raise_for_status()
            data = resp.json()
            period_start = datetime.datetime.strptime(
                data["interestFrom"], POLISH_DATE_FORMAT
            ).date()
            period_end = datetime.datetime.strptime(
                data["interestTo"], POLISH_DATE_FORMAT
            ).date()
            period_interest_rate = float(
                Decimal(data["interestRatePercentage"][:-1].replace(",", ".")) / 100
            )
            period_interest_values = []

            for year_table in data["tables"]:
                year = int(year_table["name"])
                table_headers = year_table["header"]["items"]
                month_numbers = [
                    ROMAN_NUMERALS.index(roman_month) + 1
                    for roman_month in table_headers[1:]
                ]

                for row in year_table["rows"]:
                    cells = row["items"]
                    day = int(cells[0])
                    for cell_idx, cell in enumerate(cells[1:]):
                        if not cell:
                            continue
                        cell_date = datetime.date(year, month_numbers[cell_idx], day)
                        cell_interest = float(cell.replace(",", "."))
                        period_interest_values.append((cell_date, cell_interest))
            period_interest_values.sort()
            print(
                f"{period_start};{period_end};{period_interest_rate};",
                end="",
                file=file,
            )
            print(
                " ".join(map(str, map(itemgetter(1), period_interest_values))),
                file=file,
            )

        sale_from = (
            sale_from.replace(year=sale_from.year + 1, month=1)
            if sale_from.month == 12
            else sale_from.replace(month=sale_from.month + 1)
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", help="The directory to output CSV files to.")
    parser.add_argument(
        "--bond-type",
        help="Select bond type(s) to download. Defaults to all.",
        action="append",
        choices=BOND_TYPES.keys(),
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    bond_types = args.bond_type or BOND_TYPES.keys()

    output_dir.mkdir(exist_ok=True)
    for bond_type in bond_types:
        with open(output_dir / f"{bond_type.lower()}.csv", "w") as fp:
            fetch_bond_interest_tables(bond_type, BOND_TYPES[bond_type], file=fp)


if __name__ == "__main__":
    main()
