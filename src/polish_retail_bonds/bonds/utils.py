import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal


def add_months(date: datetime.date, month_count: int) -> datetime.date:
    year, month = divmod(date.month + month_count - 1, 12)
    year += date.year
    month += 1
    _, max_day = calendar.monthrange(year, month)
    return date.replace(year=year, month=month, day=min(date.day, max_day))


def round_half_up(value: Decimal, *, exp: Decimal = Decimal("0.01")) -> Decimal:
    return value.quantize(exp, rounding=ROUND_HALF_UP)
