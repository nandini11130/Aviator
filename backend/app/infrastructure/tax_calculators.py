"""India GST rules for air travel: Economy is taxed at 5%, Business/First at
12%. Implemented as a strategy behind the `TaxCalculator` port so a future
jurisdiction (or a flat-rate test double) can be swapped in without touching
any use case.
"""
from __future__ import annotations

from app.domain.ports import TaxCalculator
from app.domain.value_objects import CabinClass, Money

_GST_RATE_PERCENT: dict[CabinClass, int] = {
    CabinClass.ECONOMY: 5,
    CabinClass.BUSINESS: 12,
    CabinClass.FIRST: 12,
}


class IndiaGstCalculator(TaxCalculator):
    def calculate(self, base_amount: Money, cabin_class: CabinClass) -> Money:
        rate = _GST_RATE_PERCENT[cabin_class]
        tax_minor = round(base_amount.amount_minor * rate / 100)
        return Money(tax_minor, base_amount.currency)


class FlatRateTaxCalculator(TaxCalculator):
    """Simple fixed-percentage calculator, handy for other jurisdictions
    or for tests that want deterministic, rate-agnostic numbers.
    """

    def __init__(self, rate_percent: int):
        self._rate_percent = rate_percent

    def calculate(self, base_amount: Money, cabin_class: CabinClass) -> Money:
        tax_minor = round(base_amount.amount_minor * self._rate_percent / 100)
        return Money(tax_minor, base_amount.currency)
