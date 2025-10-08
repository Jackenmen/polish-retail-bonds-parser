import dataclasses
import datetime
from bisect import bisect_left
from operator import itemgetter


class InterestRate:
    def __init__(
        self, *interest_periods: tuple[datetime.date, datetime.date, float]
    ) -> None:
        self.interest_periods = ()
        for period in interest_periods:
            # calling this for each interest period is likely not the optimal approach
            self._add_interest_period(*period)

    def __repr__(self) -> str:
        interest_periods_repr = ", ".join(map(repr, self.interest_periods))
        return f"{self.__class__.__name__}({interest_periods_repr})"

    def _add_interest_period(
        self, start: datetime.date, end: datetime.date, interest_rate: float
    ) -> None:
        interest_periods = []
        for period_start, period_end, period_interest_rate in self.interest_periods:
            if start > period_end or end < period_start:
                # no overlap
                interest_periods.append(
                    (period_start, period_end, period_interest_rate)
                )
                continue

            to_add = []
            if interest_rate == period_interest_rate:
                start = min(start, period_start)
                end = max(end, period_end)
            elif start >= period_start and end <= period_end:
                # added period is entirely in the currently checked period:
                # S   |-|   E or S  |---|  E or S  |--|   E or S   |--|  E
                # PS |---| PE or PS |---| PE or PS |---| PE or PS |---| PE
                to_add.append((period_start, start - datetime.timedelta(days=1)))
                to_add.append((end + datetime.timedelta(days=1), period_end))
            else:
                # added period starts earlier than currently checked period:
                # S  |--|   E
                # PS  |--| PE
                if start <= period_start:
                    period_start = end + datetime.timedelta(days=1)
                # added period ends later than currently checked period:
                # S   |--|  E
                # PS |--|  PE
                if end >= period_end:
                    period_end = start - datetime.timedelta(days=1)
                # both of the above at once give:
                # S  |---| E or S  |--|  E or S  |--| E
                # PS  |-| PE or PS  |-| PE or PS |-| PE
                to_add.append((period_start, period_end))

            for period_start, period_end in to_add:
                if period_start < period_end:
                    interest_periods.append(
                        (period_start, period_end, period_interest_rate)
                    )

        interest_periods.append((start, end, interest_rate))
        self.interest_periods = tuple(interest_periods)

    def __getitem__(self, key: datetime.date) -> float:
        for period_start, period_end, interest_rate in self.interest_periods:
            if period_start <= key <= period_end:
                return interest_rate
        raise KeyError(key)


@dataclasses.dataclass
class Bond:
    type_name: str
    _: dataclasses.KW_ONLY
    series_name: str
    isin: str
    sale_from: datetime.date
    sale_to: datetime.date
    redemption_date: datetime.date
    interest_rate: InterestRate
    has_compound_interest: bool
    early_redemption_cost: float
    values: list[float] = dataclasses.field(default_factory=list)


def create_tos_bond(
    *,
    series_name: str,
    isin: str,
    sale_from: datetime.date,
    sale_to: datetime.date,
    interest_rate: InterestRate | float,
) -> Bond:
    redemption_date = sale_from.replace(year=sale_from.year + 3)
    bond = Bond(
        "TOS",
        series_name=series_name,
        isin=isin,
        sale_from=sale_from,
        sale_to=sale_to,
        redemption_date=sale_from.replace(year=sale_from.year + 3),
        interest_rate=(
            interest_rate
            if isinstance(interest_rate, InterestRate)
            else InterestRate((sale_from, redemption_date, interest_rate))
        ),
        has_compound_interest=True,
        # this will be input argument in the future
        early_redemption_cost=(
            0.7
            if datetime.date(2015, 4, 1) <= sale_from <= datetime.date(2024, 8, 31)
            else 1.0
        ),
    )
    # The goal here is to calculate values consistent with interest tables.
    # The early redemption value formula shown in the emission letter rounds
    # bond's interest from previous periods which does not seem to be the case
    # with the values in the interest tables so the actual sale value could differ
    # slightly...
    nominal_value = 100
    for period in range(3):
        # Periods in the TOS interest tables do not actually overlap (since TOS0526
        # emission) *but* the way the actual interest is calculated is more intuitive
        # with overlapping periods.
        period_start = bond.sale_from.replace(
            year=bond.sale_from.year + period
        )
        period_end = period_start.replace(year=period_start.year + 1)
        # Number of interest-eligible days in the period to put in the formula.
        # First day of each period has to be excluded since it's either:
        # - value at the date of the purchase (interest accrues starting on day 2)
        # - value at the end of the previous period
        # Basically, the value on day N is the interest for the days that elapsed (N-1).
        period_days = (period_end - period_start).days

        # First day of the period is the last day of the previous period so it has to
        # be excluded unless this is the first period.
        # `day_count == 0` for the first day of each period so the interest will be 0
        # as expected for overlapping periods.
        for day_count in range(period != 0, period_days + 1):
            day_date = period_start + datetime.timedelta(days=day_count)
            multiplicand = 1 + bond.interest_rate[day_date] * day_count / period_days
            day_value = nominal_value * multiplicand
            bond.values.append(round(day_value, 2))

        # Update nominal value for next period
        if bond.has_compound_interest:
            nominal_value = day_value

    return bond
