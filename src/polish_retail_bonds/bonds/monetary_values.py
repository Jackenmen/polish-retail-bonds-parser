import dataclasses
import datetime
from collections.abc import Iterable
from decimal import Decimal
from typing import overload


@dataclasses.dataclass
class MonetaryValues:
    """
    A collection of monetary values keyed by date.

    Underlying representation (`values`) is a sequence of monetary values
    indexed by number of days since `start`.
    """

    start: datetime.date
    end: datetime.date
    #: Values on each day this instance refers to.
    #: ``values[0]`` is value on the `start` day, values[-1] is value on the `end` day.
    values: list[Decimal] = dataclasses.field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.values)

    def __iter__(self) -> Iterable[Decimal]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    @overload
    def __getitem__(self, key: datetime.date) -> Decimal: ...

    @overload
    def __getitem__(self, key: slice) -> MonetaryValues: ...

    def __getitem__(self, key: datetime.date | slice) -> Decimal | MonetaryValues:
        if not self.values:
            raise TypeError("The interest values for this period are not known yet.")
        if isinstance(key, slice):
            if key.step is not None and key.step != 1:
                raise TypeError("non-default slice step is not supported")
            start = max(key.start, self.start)
            end = min(key.stop, self.end)
            if start >= end:
                return MonetaryValues(key.start, key.stop)
            start_idx = (start - self.start).days
            end_idx = (end - self.start).days
            return MonetaryValues(key.start, key.stop, self.values[start_idx:end_idx])

        if key < self.start or key > self.end:
            raise KeyError(key)
        return self.values[(key - self.start).days]

    def get[T](self, key: datetime.date, default: T = None) -> Decimal | T:
        if not self.values:
            raise TypeError("The interest values for this period are not known yet.")
        if key < self.start or key > self.end:
            return default
        return self.values[(key - self.start).days]
