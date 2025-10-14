import datetime
from bisect import insort
from decimal import Decimal


class InterestRate:
    def __init__(
        self, *interest_periods: tuple[datetime.date, datetime.date, Decimal]
    ) -> None:
        self.interest_periods = ()
        for period in interest_periods:
            # calling this for each interest period is likely not the optimal approach
            self._add_interest_period(*period)

    def __repr__(self) -> str:
        interest_periods_repr = ", ".join(map(repr, self.interest_periods))
        return f"{self.__class__.__name__}({interest_periods_repr})"

    @property
    def start(self) -> datetime.date:
        return self.interest_periods[0][0]

    @property
    def end(self) -> datetime.date:
        return self.interest_periods[-1][1]

    def _add_interest_period(
        self, start: datetime.date, end: datetime.date, interest_rate: Decimal
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
                start, end = end, start
                to_add.append((period_start, period_end))
            else:
                # added period starts earlier than currently checked period:
                # S  |--|   E
                # PS  |--| PE
                if start <= period_start:
                    end = period_start - datetime.timedelta(days=1)
                # added period ends later than currently checked period:
                # S   |--|  E
                # PS |--|  PE
                if end >= period_end:
                    start = period_end + datetime.timedelta(days=1)
                # both of the above at once give:
                # S  |---| E or S  |--|  E or S  |--| E
                # PS  |-| PE or PS  |-| PE or PS |-| PE
                to_add.append((period_start, period_end))

            for period_start, period_end in to_add:
                if period_start < period_end:
                    interest_periods.append(
                        (period_start, period_end, period_interest_rate)
                    )

        if start < end:
            insort(interest_periods, (start, end, interest_rate))
        self.interest_periods = tuple(interest_periods)

    def __getitem__(self, key: datetime.date) -> Decimal:
        for period_start, period_end, interest_rate in self.interest_periods:
            if period_start <= key <= period_end:
                return interest_rate
        raise KeyError(key)

    def __contains__(self, key: datetime.date) -> bool:
        for period_start, period_end, interest_rate in self.interest_periods:
            if period_start <= key <= period_end:
                return True
        return False
