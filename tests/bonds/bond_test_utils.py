import datetime
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

from polish_retail_bonds.bonds import Bond, InterestPeriod, InterestRate
from polish_retail_bonds.bonds.utils import add_months

DATASETS_DIR = Path(__file__).parent.absolute() / "data"


def bond_id(bond: Bond) -> str:
    return bond.series_name


def load_test_cases(filename: str) -> Bond:
    with open(DATASETS_DIR / filename, encoding="utf-8") as fp:
        it = (line for line in fp if line)
        for line in it:
            series_parts = line.strip().split(";")
            series_name = series_parts[0]
            series_sale_from = datetime.date.fromisoformat(series_parts[1])
            series_sale_to = datetime.date.fromisoformat(series_parts[2])
            series_redemption_date = datetime.date.fromisoformat(series_parts[3])
            is_yearly = series_parts[4] == "Y"
            period_count = int(series_parts[5])
            has_compound_interest = series_parts[6] == "C"
            processed_until = series_sale_from
            last_processed_value = Decimal(0)
            interest_rates = []
            interest_periods = []
            months_per_period = 12 if is_yearly else 1

            for period, period_line in zip(range(period_count), it):
                period_line = period_line.strip()
                if not period_line:
                    period_start = add_months(series_sale_from, period * months_per_period)
                    period_end = add_months(series_sale_from, (period + 1) * months_per_period)
                    interest_periods.append(InterestPeriod(period_start, period_end))
                    continue
                period_parts = period_line.split(";")
                period_start = datetime.date.fromisoformat(period_parts[0])
                period_end = datetime.date.fromisoformat(period_parts[1])
                period_interest_rate = Decimal(period_parts[2])
                period_values = [
                    Decimal(value) - last_processed_value
                    for value in period_parts[3].split(" ")
                ]
                if period_start != processed_until:
                    period_values.insert(0, Decimal())

                period = InterestPeriod(
                    period_start.replace(day=1), period_end, period_values
                )
                interest_rates.append((period_start, period_end, period_interest_rate))
                interest_periods.append(period)

                processed_until = period_end
                if has_compound_interest:
                    last_processed_value += period_values[-1]

            yield Bond(
                series_name[:3],
                series_name=series_name,
                isin="",
                sale_from=series_sale_from,
                sale_to=series_sale_to,
                redemption_date=series_redemption_date,
                interest_rate=InterestRate(*interest_rates),
                has_compound_interest=has_compound_interest,
                early_redemption_cost=Decimal(1),
                interest_periods=tuple(interest_periods),
            )


def assert_common_bond_traits(bond: Bond) -> None:
    """Sanity check common traits of bond's derived properties."""

    # assert that earned_interest == (accrued_interest + paid_interest)
    assert bond.earned_interest_values.values == [
        a + b for a, b in zip(bond.accrued_interest_values, bond.paid_interest_values)
    ]

    actual_total_values = bond.total_values
    actual_total_redemption_values = bond.total_redemption_values

    # number of values should be equal to number of days
    # between sale and redemption date
    expected_length = (bond.interest_rate.end - bond.sale_from).days + 1
    assert len(bond.earned_interest_values) == expected_length
    assert len(bond.accrued_interest_values) == expected_length
    assert len(bond.paid_interest_values) == expected_length
    assert len(actual_total_values) == expected_length
    assert len(actual_total_redemption_values) == expected_length

    # number of decimal points should never exceed 2
    ndigits = 2
    assert_decimal_digits(bond.earned_interest_values, ndigits)
    assert_decimal_digits(bond.accrued_interest_values, ndigits)
    assert_decimal_digits(bond.paid_interest_values, ndigits)
    assert_decimal_digits(actual_total_values, ndigits)
    assert_decimal_digits(actual_total_redemption_values, ndigits)
    for period in bond.interest_periods:
        assert_decimal_digits(period, ndigits)
    assert_decimal_digits((bond.early_redemption_cost,), ndigits)
    assert_decimal_digits((bond.nominal_value,), ndigits)
    assert_decimal_digits((bond.total_interest,), ndigits)

    # total interest is the interest earned until redemption date
    assert bond.total_interest == bond.earned_interest_values.values[-1]

    first_period = bond.interest_periods[0]
    # bond's redemption value cannot be lower than nominal value in first period
    assert all(
        value >= bond.nominal_value
        for value in actual_total_redemption_values[first_period.start:first_period.end]
    )

    # difference between bond value and its actual redemption value should be equal to
    # its early redemption cost
    day_before_end = actual_total_redemption_values.end - datetime.timedelta(days=1)
    actual_redemption_value = actual_total_redemption_values[day_before_end]
    expected_redemption_value = (
        actual_total_values[day_before_end] - bond.early_redemption_cost
    )
    if first_period.start <= day_before_end <= first_period.end:
        expected_redemption_value = max(bond.nominal_value, expected_redemption_value)
    assert actual_redemption_value == expected_redemption_value


def assert_simple_interest_bond_traits(bond: Bond) -> None:
    """
    Sanity check traits of derived properties specific to bonds with simple interest.
    """

    periods_with_known_interest = [
        period for period in bond.interest_periods if period.values
    ]
    actual_accrued_interest_values = bond.accrued_interest_values
    actual_paid_interest_values = bond.paid_interest_values
    actual_total_redemption_values = bond.total_redemption_values
    for idx, period in enumerate(periods_with_known_interest):
        # accrued interest on the last day of the period should be 0 (as it's paid out)
        assert actual_accrued_interest_values[period.end] == 0

        # paid interest should be equivalent for all days but the last one
        expected_value = actual_paid_interest_values[
            period.end - datetime.timedelta(days=1)
        ]
        assert all(
            actual_value == expected_value
            for actual_value in actual_paid_interest_values[period.start : period.end]
        )

        # interest paid on last day of the period should be equivalent to
        # period's total interest
        paid_interest = actual_paid_interest_values[period.end] - expected_value
        assert paid_interest == period.total_interest

        # total value of the bond at the end of each period should be equal to
        # its nominal value (as interest is paid out)
        assert bond.total_values[period.end] == bond.nominal_value
        # bond's total redemption value at the end of each period should be equal to
        # its nominal value reduced by its redemption cost (except for redemption date)
        expected_redemption_value = (
            bond.nominal_value
            if period.end == bond.redemption_date
            else bond.nominal_value - bond.early_redemption_cost
        )
        assert actual_total_redemption_values[period.end] == expected_redemption_value

    # bond's redemption value at the end of first period should be its nominal value
    # minus its early redemption cost
    first_period = bond.interest_periods[0]
    expected_redemption_value = bond.nominal_value - bond.early_redemption_cost
    assert actual_total_redemption_values[first_period.end] == expected_redemption_value


def assert_compound_interest_bond_traits(bond: Bond) -> None:
    """
    Sanity check traits of derived properties specific to bonds with compound interest.
    """

    # accrued interest == earned interest for bonds with compound interest
    assert bond.accrued_interest_values == bond.earned_interest_values

    # paid interest is zero on all days for bonds with compound interest
    assert all(value == 0.0 for value in bond.paid_interest_values)

    actual_total_values = bond.total_values
    actual_total_redemption_values = bond.total_redemption_values
    # last value in total values should be equal to
    # a sum of bond's nominal value and total interest
    expected_total_value = bond.nominal_value + bond.total_interest
    assert actual_total_values.values[-1] == expected_total_value
    expected_redemption_value = (
        expected_total_value - bond.early_redemption_cost
        if bond.has_missing_interest_rates
        else expected_total_value
    )
    assert actual_total_redemption_values.values[-1] == expected_redemption_value

    # difference between bond value and its actual redemption value
    # at the end of first period should be equal to its early redemption cost
    first_period = bond.interest_periods[0]
    expected_redemption_value = (
        actual_total_values[first_period.end] - bond.early_redemption_cost
    )
    assert actual_total_redemption_values[first_period.end] == expected_redemption_value


def assert_decimal_digits(iterable: Iterable[Decimal], ndigits: int) -> None:
    for value in iterable:
        assert str(value)[::-1].find(".") <= ndigits
