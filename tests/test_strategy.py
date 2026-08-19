from decimal import Decimal

import pytest

from gridbot.models import Instrument
from gridbot.strategy import floor_to_step, make_levels, make_plan


def instrument() -> Instrument:
    return Instrument(
        symbol="BTCUSDT",
        base_coin="BTC",
        quote_coin="USDT",
        tick_size=Decimal("0.1"),
        qty_step=Decimal("0.00001"),
        min_qty=Decimal("0.00001"),
        max_qty=Decimal("10"),
        min_amount=Decimal("1"),
    )


def test_floor_to_step_never_rounds_up() -> None:
    assert floor_to_step(Decimal("1.239"), Decimal("0.01")) == Decimal("1.23")


def test_arithmetic_levels_include_bounds() -> None:
    levels = make_levels(Decimal("90"), Decimal("110"), 4, Decimal("0.1"))
    assert levels == [Decimal("90"), Decimal("95"), Decimal("100"), Decimal("105"), Decimal("110")]


def test_plan_places_buys_below_and_sells_above() -> None:
    levels = [Decimal("90"), Decimal("95"), Decimal("100"), Decimal("105")]
    plan = make_plan(levels, Decimal("99"), Decimal("10"), instrument())
    assert [item.side for item in plan] == ["Buy", "Buy", "Sell", "Sell"]


def test_plan_rejects_too_small_orders() -> None:
    with pytest.raises(ValueError, match="min qty"):
        make_plan([Decimal("100000")], Decimal("90000"), Decimal("0.1"), instrument())
