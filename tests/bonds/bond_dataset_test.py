import datetime
from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest

from polish_retail_bonds.bonds import Bond, InterestRate, create_tos_bond


PKG_DIR = Path(__file__).parent.absolute()


def _load_test_cases() -> Bond:
    with open(PKG_DIR / "tos.csv", encoding="utf-8") as fp:
        it = (line for line in fp if line)
        for line in it:
            series_parts = line.split(";")
            series_name = series_parts[0]
            series_sale_from = datetime.date.fromisoformat(series_parts[1])
            series_sale_to = datetime.date.fromisoformat(series_parts[2])
            series_redemption_date = datetime.date.fromisoformat(series_parts[3])
            period_count = int(series_parts[5])
            values = []
            processed_until = series_sale_from - datetime.timedelta(days=1)
            interest_rates = []

            for period, period_line in zip(range(period_count), it):
                period_parts = period_line.split(";")
                period_start = datetime.date.fromisoformat(period_parts[0])
                period_end = datetime.date.fromisoformat(period_parts[1])
                period_interest_rate = float(period_parts[2])
                interest_rates.append((period_start, period_end, period_interest_rate))
                period_values = [
                    float(100 + Decimal(value))
                    for value in period_parts[3].split(" ")[(period_start == processed_until):]
                ]
                values.extend(period_values)
                processed_until = period_end

            yield Bond(
                "TOS",
                series_name=series_name,
                isin="",
                sale_from=series_sale_from,
                sale_to=series_sale_to,
                redemption_date=series_sale_from.replace(
                    year=series_sale_from.year + 3
                ),
                interest_rate=InterestRate(*interest_rates),
                has_compound_interest=True,
                early_redemption_cost=1.0,
                values=values,
            )


@pytest.mark.parametrize("expected", _load_test_cases(), ids=lambda b: b.series_name)
def test_tos_values(expected: Bond) -> None:
    actual = create_tos_bond(
        series_name=expected.series_name,
        isin=expected.isin,
        sale_from=expected.sale_from,
        sale_to=expected.sale_to,
        interest_rate=expected.interest_rate,
    )

    assert actual.redemption_date == expected.redemption_date
    assert actual.values == expected.values
