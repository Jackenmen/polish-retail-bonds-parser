import datetime
from collections.abc import Iterable
from decimal import Decimal

from .bond import Bond, InterestPeriod
from .interest_rate import InterestRate
from .utils import add_months, round_half_up


def create_ror_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_monthly_periods(sale_from, 1 * 12)
    bond = Bond(
        "ROR",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 1),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=False,
        # this will be input argument in the future
        early_redemption_cost=Decimal("0.5"),
        interest_periods=interest_periods,
    )
    _fill_values(bond, is_monthly=True)
    return bond


def create_dor_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_monthly_periods(sale_from, 2 * 12)
    bond = Bond(
        "DOR",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 2),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=False,
        # this will be input argument in the future
        early_redemption_cost=Decimal("0.7"),
        interest_periods=interest_periods,
    )
    _fill_values(bond, is_monthly=True)
    return bond


def create_tos_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Decimal,
) -> Bond:
    interest_periods = _generate_yearly_periods(sale_from, 3)
    bond = Bond(
        "TOS",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 3),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=True,
        # this will be input argument in the future
        early_redemption_cost=(
            Decimal("0.7")
            if datetime.date(2015, 4, 1) <= sale_from <= datetime.date(2024, 8, 31)
            else Decimal(1)
        ),
        interest_periods=interest_periods,
    )
    _fill_values(bond)
    return bond


def create_coi_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_yearly_periods(sale_from, 4)
    bond = Bond(
        "COI",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 4),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=False,
        # this will be input argument in the future
        early_redemption_cost=(
            Decimal(2)
            if sale_from >= datetime.date(2024, 9, 1)
            else Decimal("0.7")
            if sale_from >= datetime.date(2015, 4, 1)
            else Decimal(1)
            if sale_from >= datetime.date(2010, 5, 1)
            else Decimal("0.5")
            if sale_from >= datetime.date(2003, 3, 1)
            else Decimal(1)
            if sale_from >= datetime.date(2002, 10, 1)
            else Decimal("1.5")
            if sale_from >= datetime.date(2002, 8, 1)
            else Decimal(2)
            if sale_from >= datetime.date(2002, 2, 1)
            else Decimal(3)
        ),
        interest_periods=interest_periods,
    )
    _fill_values(bond)
    return bond


def create_edo_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_yearly_periods(sale_from, 10)
    bond = Bond(
        "EDO",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 10),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=True,
        # this will be input argument in the future
        early_redemption_cost=(
            Decimal(3)
            if sale_from >= datetime.date(2024, 9, 1)
            else Decimal(2)
            if sale_from >= datetime.date(2010, 5, 1)
            else Decimal(1)
        ),
        interest_periods=interest_periods,
    )
    _fill_values(bond)
    return bond


def create_ros_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_yearly_periods(sale_from, 6)
    bond = Bond(
        "ROS",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 6),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=True,
        # this will be input argument in the future
        early_redemption_cost=(
            Decimal(2) if sale_from >= datetime.date(2024, 9, 1) else Decimal("0.7")
        ),
        interest_periods=interest_periods,
    )
    _fill_values(bond)
    return bond


def create_rod_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | Iterable[Decimal],
) -> Bond:
    interest_periods = _generate_yearly_periods(sale_from, 12)
    bond = Bond(
        "ROD",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 12),
        interest_rate=_cast_to_interest_rate(interest_periods, interest_rate),
        has_compound_interest=True,
        # this will be input argument in the future
        early_redemption_cost=(
            Decimal(3) if sale_from >= datetime.date(2024, 9, 1) else Decimal(2)
        ),
        interest_periods=interest_periods,
    )
    _fill_values(bond)
    return bond


def _cast_to_interest_rate(
    interest_periods: tuple[InterestPeriod, ...],
    interest_rate: InterestRate | Iterable[Decimal] | Decimal,
) -> InterestRate:
    if isinstance(interest_rate, InterestRate):
        return interest_rate
    if isinstance(interest_rate, Decimal):
        return InterestRate(
            *((period.start, period.end, interest_rate) for period in interest_periods)
        )
    return InterestRate(
        *(
            (interest_periods[period_idx].start, interest_periods[period_idx].end, apr)
            for period_idx, apr in enumerate(interest_rate)
        )
    )


def _generate_monthly_periods(
    sale_from: datetime.date, period_count: int
) -> tuple[InterestPeriod, ...]:
    return tuple(
        InterestPeriod(
            add_months(sale_from, period_idx),
            add_months(sale_from, period_idx + 1),
        )
        for period_idx in range(period_count)
    )


def _generate_yearly_periods(
    sale_from: datetime.date, period_count: int
) -> tuple[InterestPeriod, ...]:
    return tuple(
        InterestPeriod(
            sale_from.replace(year=sale_from.year + period_idx),
            sale_from.replace(year=sale_from.year + period_idx + 1),
        )
        for period_idx in range(period_count)
    )


def _fill_values(bond: Bond, *, is_monthly: bool = False) -> None:
    # The goal here is to calculate values consistent with interest tables.
    # The early redemption value formula shown in the emission letter rounds
    # bond's interest from previous periods which does not seem to be the case
    # with the values in the interest tables so the actual sale value could differ
    # slightly...
    base_value = bond.nominal_value
    # NOTE:
    # For TOS, periods in the interest tables do not actually overlap (since TOS0526
    # emission) *but* the way the actual interest is calculated is consistent with
    # the earlier emissions that had overlapping periods.
    for period in bond.interest_periods:
        if period.end not in bond.interest_rate:
            continue
        # Number of interest-eligible days in the period to put in the formula.
        # First day of each period has to be excluded since it's either:
        # - value at the date of the purchase (interest accrues starting on day 2)
        # - value at the end of the previous period
        # Basically, the value on day N is the interest for the days that elapsed (N-1).
        period_days = (period.end - period.start).days
        denominator = period_days
        if is_monthly:
            denominator *= 12

        # `day_count == 0` for the first day of each period so the interest will be 0
        # as expected for overlapping periods.
        day_value = base_value
        for day_count in range(period_days + 1):
            day_date = period.start + datetime.timedelta(days=day_count)
            multiplicand = 1 + bond.interest_rate[day_date] * day_count / denominator
            day_value = base_value * multiplicand
            period.values.append(round_half_up(round_half_up(day_value) - base_value))

        # Update nominal value for next period
        if bond.has_compound_interest:
            base_value = day_value
