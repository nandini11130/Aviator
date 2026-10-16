"""Value objects: immutable, equality-by-value types with zero behaviour
leaking from the domain. Money is modelled in integer minor units (paise)
so pricing math never touches floating point.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CabinClass(str, Enum):
    ECONOMY = "ECONOMY"
    BUSINESS = "BUSINESS"
    FIRST = "FIRST"


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int  # smallest currency unit, e.g. paise
    currency: str = "INR"

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("Money amount cannot be negative")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    @property
    def major_units(self) -> float:
        return self.amount_minor / 100

    @classmethod
    def from_major(cls, amount: float, currency: str = "INR") -> "Money":
        return cls(round(amount * 100), currency)

    def to_dict(self) -> dict:
        return {"amount_minor": self.amount_minor, "currency": self.currency}


@dataclass(frozen=True, slots=True)
class PriceBreakdown:
    token_amount: Money
    tax_amount: Money

    @property
    def total(self) -> Money:
        return self.token_amount + self.tax_amount

    def to_dict(self) -> dict:
        return {
            "token_amount": self.token_amount.to_dict(),
            "tax_amount": self.tax_amount.to_dict(),
            "total": self.total.to_dict(),
        }
