import dataclasses
from decimal import Decimal

from .interest_rate import InterestRate
from .monetary_values import MonetaryValues


class InterestPeriod(MonetaryValues):
    """Bond interest period."""

    @property
    def total_interest(self) -> Decimal:
        """
        Interest earned in the period that this instance refers to.

        This will return 0.0, if the interest values (and rate) are not yet known.
        """
        return self.values[-1] if self.values else Decimal()


# Earned interest  - interest earned on the bond over a specific period
# Accrued interest - interest that the bond has earned but has not been paid out yet
# Paid interest    - interest that has already been received as payment
#
# earned_interest == (accrued_interest + paid_interest)
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
    early_redemption_cost: Decimal
    interest_periods: tuple[InterestPeriod, ...]
    nominal_value: Decimal = Decimal(100)

    @property
    def has_missing_interest_rates(self) -> bool:
        """Indicates whether interest rate for some periods is not yet known."""
        return any(not period.values for period in self.interest_periods)

    @property
    def total_interest(self) -> Decimal:
        """
        Total interest earned (accrued + paid) on the bond.

        This is equivalent to ``bond.earned_interest_values.values[-1]``
        but doesn't require calculation of individual values.

        If `has_missing_interest_rates` is `False`, this is the interest
        that will be paid in addition to bond's nominal value at redemption date.
        Otherwise, only periods with known interest rate are included.
        """
        return sum(period.total_interest for period in self.interest_periods)

    @property
    def earned_interest_values(self) -> MonetaryValues:
        """
        Values of the total interest earned (accrued + paid)
        between `sale_from` and the given day.

        If `has_missing_interest_rates` is `False`, this will include
        total interest earned for each day from `sale_from` to `redemption_date`.
        Otherwise, only periods with known interest rate are included.

        Example values:
        - bond with compound interest (e.g. TOS, EDO):
          0.0, 0.01, 0.03, ..., 5.39, 5.4 (end of period), 5.42, 5.43, 5.45, ...
        - bond with no compound interest (e.g. OTS, ROR, DOR, COI)
          0.0, 0.01, 0.03, ..., 5.39, 5.4 (end of period), 5.42, 5.43, 5.45, ...
        """
        values = [Decimal()]
        start = self.interest_periods[0].start
        end = start
        for period in self.interest_periods:
            if not period.values:
                break
            end = period.end
            base_value = values[-1]
            it = iter(period.values)
            next(it)
            values.extend(base_value + interest for interest in it)
        return MonetaryValues(start, end, values)

    @property
    def accrued_interest_values(self) -> MonetaryValues:
        """
        Values of the accrued (not yet paid) interest until the given day.

        If `has_missing_interest_rates` is `False`, this will include
        total accrued interest for each day from `sale_from` to `redemption_date`.
        Otherwise, only periods with known interest rate are included.

        Example values:
        - bond with compound interest (e.g. TOS, EDO):
          0.0, 0.01, ..., 5.39, 5.4 (end of period), 5.42, 5.43, ...,
          ..., 17.07, 17.09 (redemption date)
        - bond with no compound interest (e.g. OTS, ROR, DOR, COI)
          0.0, 0.01, ..., 5.39, 0.0 (end of period), 0.02, 0.03, ...,
          ..., 5.98, 0.0 (redemption date)
          TODO: should end of period be 0 or the amount about to be paid out?
        """
        values = [Decimal()]
        start = self.interest_periods[0].start
        end = start
        for period in self.interest_periods:
            if not period.values:
                break
            end = period.end
            base_value = values[-1]
            it = iter(period.values)
            next(it)
            values.extend(base_value + interest for interest in it)
            if not self.has_compound_interest:
                values[-1] = Decimal()
        return MonetaryValues(start, end, values)

    @property
    def paid_interest_values(self) -> MonetaryValues:
        """
        Values of the paid interest until the given day.

        If `has_missing_interest_rates` is `False`, this will include
        total paid interest for each day from `sale_from` to `redemption_date`.
        Otherwise, only periods with known interest rate are included.

        Example values:
        - bond with compound interest (e.g. TOS, EDO):
          0.0, ..., 0.0, 0.0 (end of period), 0.0, ..., 0.0, 0.0 (redemption date)
        - bond with no compound interest (e.g. OTS, ROR, DOR, COI)
          0.0, ..., 0.0, 5.4 (end of period), 5.4, 5.4, ..., 5.4, 11.4 (redemption date)
          TODO: should end of period be 0 or the amount about to be paid out?
        """
        values = [Decimal()]
        start = self.interest_periods[0].start
        end = start
        for period in self.interest_periods:
            if not period.values:
                break
            end = period.end
            base_value = values[-1]
            values.extend(base_value for _ in range(len(period.values) - 1))
            if not self.has_compound_interest:
                values[-1] = base_value + period.total_interest
        return MonetaryValues(start, end, values)

    @property
    def total_values(self) -> MonetaryValues:
        """
        Total values (nominal value + values of accrued interest) of the bond
        between `sale_from` and the given day.

        See `total_redemption_values` for the value that the bond can actually
        be redeemed at on the given day.

        If `has_missing_interest_rates` is `False`, this will include
        total values for each day from `sale_from` to `redemption_date`.
        Otherwise, only periods with known interest rate are included.

        Example values:
        - bond with compound interest (e.g. TOS, EDO):
          100.0, 100.01, ..., 105.39, 105.4 (end of period), 105.42, 105.43, ...,
          ..., 117.07, 117.09 (redemption date)
        - bond with no compound interest (e.g. OTS, ROR, DOR, COI)
          100.0, 100.01, ..., 105.39, 100.0 (end of period), 100.02, 100.03, ...
        """
        accrued_interest_values = self.accrued_interest_values
        return MonetaryValues(
            accrued_interest_values.start,
            accrued_interest_values.end,
            [self.nominal_value + value for value in accrued_interest_values],
        )

    @property
    def total_redemption_values(self) -> MonetaryValues:
        """
        Total values that the bond can actually be redeemed at on the given day,
        i.e. nominal value + values of accrued interest, reduced by the early redemption
        cost, if applicable.

        See `total_values` for the bond's value excluding the early redemption cost.

        If `has_missing_interest_rates` is `False`, this will include
        total values for each day from `sale_from` to `redemption_date`.
        Otherwise, only periods with known interest rate are included.

        Example values:
        - bond with compound interest (e.g. TOS, EDO):
          100.0, 100.0, ..., 100.0, 100.01 (interest > redemption cost), 100.03, ...,
          ..., 103.39, 103.4 (end of period), 103.42, 103.43, ...,
          ..., 115.06, 116.07, 117.09 (redemption date)
        - bond with no compound interest (e.g. OTS, ROR, DOR, COI)
          100.0, 100.0, ..., 100.0, 100.01 (interest > redemption cost), 100.03, ...,
          ..., 103.39, 98.0 (end of period), 98.02, 98.03, ...,
          ..., 103.97, 103.98, 98.0 (redemption date)
        """
        if self.has_compound_interest:
            total_values = self.total_values
            values = [
                max(self.nominal_value, value - self.early_redemption_cost)
                for value in total_values
            ]
            if total_values.end == self.redemption_date:
                values[-1] = total_values.values[-1]
            return MonetaryValues(total_values.start, total_values.end, values)

        it = iter(self.interest_periods)
        first_period = next(it)
        values = [
            self.nominal_value + max(Decimal(), value - self.early_redemption_cost)
            for value in first_period
        ]
        base_value = self.nominal_value - self.early_redemption_cost
        values[-1] = base_value
        start = first_period.start
        end = first_period.end

        for period in it:
            if not period.values:
                break
            end = period.end
            it = iter(period.values)
            next(it)
            values.extend(base_value + interest for interest in it)
            values[-1] = base_value

        if end == self.redemption_date:
            values[-1] += self.early_redemption_cost

        return MonetaryValues(start, end, values)
