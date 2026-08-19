from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from .models import Instrument, PlannedOrder


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def nearest_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_HALF_UP) * step


def make_levels(lower: Decimal, upper: Decimal, intervals: int, tick: Decimal) -> list[Decimal]:
    spacing = (upper - lower) / Decimal(intervals)
    levels = [nearest_to_step(lower + spacing * i, tick) for i in range(intervals + 1)]
    if len(set(levels)) != len(levels):
        raise ValueError("Grid is too dense for this symbol's tick size")
    return levels


def make_plan(
    levels: list[Decimal],
    market_price: Decimal,
    quote_per_order: Decimal,
    instrument: Instrument,
) -> list[PlannedOrder]:
    plan: list[PlannedOrder] = []
    for index, price in enumerate(levels):
        if price == market_price:
            continue
        side = "Buy" if price < market_price else "Sell"
        qty = floor_to_step(quote_per_order / price, instrument.qty_step)
        if qty < instrument.min_qty:
            raise ValueError(
                f"Order at {price} rounds to {qty}, below min qty {instrument.min_qty}; "
                "increase GRID_QUOTE_PER_ORDER"
            )
        if instrument.max_qty and qty > instrument.max_qty:
            raise ValueError(f"Order qty {qty} exceeds max qty {instrument.max_qty}")
        if price * qty < instrument.min_amount:
            raise ValueError(
                f"Order value {price * qty} is below minimum {instrument.min_amount}; "
                "increase GRID_QUOTE_PER_ORDER"
            )
        plan.append(PlannedOrder(index, side, price, qty))
    return plan


def decimal_text(value: Decimal) -> str:
    return format(value, "f")

