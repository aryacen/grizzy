from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Instrument:
    symbol: str
    base_coin: str
    quote_coin: str
    tick_size: Decimal
    qty_step: Decimal
    min_qty: Decimal
    max_qty: Decimal
    min_amount: Decimal


@dataclass(frozen=True)
class PlannedOrder:
    level: int
    side: str
    price: Decimal
    qty: Decimal


@dataclass
class TrackedOrder:
    order_id: str
    link_id: str
    level: int
    side: str
    price: str
    qty: str
    status: str = "New"
    replacement_placed: bool = False
    replacement_qty: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "TrackedOrder":
        return cls(**value)
