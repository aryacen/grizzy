from decimal import Decimal

from gridbot.bot import GridBot
from gridbot.config import Settings
from gridbot.models import Instrument


class FakeExchange:
    def __init__(self) -> None:
        self.market = Decimal("100")
        self.placed: list[dict] = []
        self.updates: dict[str, dict] = {}

    def instrument(self, symbol: str) -> Instrument:
        return Instrument(
            symbol=symbol,
            base_coin="BTC",
            quote_coin="USDT",
            tick_size=Decimal("1"),
            qty_step=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            max_qty=Decimal("10"),
            min_amount=Decimal("1"),
        )

    def last_price(self, symbol: str) -> Decimal:
        return self.market

    def balances(self, coins: list[str]) -> dict[str, Decimal]:
        return {"BTC": Decimal("10"), "USDT": Decimal("10000")}

    def place_limit(self, symbol: str, side: str, qty: str, price: str, link_id: str):
        order_id = f"order-{len(self.placed) + 1}"
        self.placed.append({"id": order_id, "side": side, "qty": qty, "price": price})
        return order_id, link_id

    def order_updates(self, symbol: str) -> dict[str, dict]:
        return self.updates


def settings(tmp_path) -> Settings:
    return Settings(
        api_key="key",
        api_secret="secret",
        testnet=True,
        execute=True,
        mainnet_confirm="",
        symbol="BTCUSDT",
        lower_price=Decimal("90"),
        upper_price=Decimal("110"),
        intervals=2,
        quote_per_order=Decimal("10"),
        poll_seconds=1,
        order_prefix="testgrid",
        state_file=tmp_path / "state.json",
    )


def test_fill_places_opposite_order_at_adjacent_level(tmp_path) -> None:
    exchange = FakeExchange()
    bot = GridBot(settings(tmp_path), exchange)
    bot.initialize()
    assert [(o["side"], o["price"]) for o in exchange.placed] == [
        ("Buy", "90"),
        ("Sell", "110"),
    ]

    buy = bot.state.orders[0]
    exchange.updates[buy.order_id] = {"orderStatus": "Filled"}
    exchange.market = Decimal("95")
    bot.reconcile()

    assert exchange.placed[-1]["side"] == "Sell"
    assert exchange.placed[-1]["price"] == "100"
    assert buy.replacement_placed is True


def test_restart_rejects_changed_grid(tmp_path) -> None:
    exchange = FakeExchange()
    original = settings(tmp_path)
    GridBot(original, exchange).state.save(original.state_file)
    changed = Settings(**{**original.__dict__, "upper_price": Decimal("120")})

    try:
        GridBot(changed, exchange)
        assert False, "expected changed grid to fail"
    except ValueError as exc:
        assert "do not match" in str(exc)


def test_partial_initialization_does_not_duplicate_recorded_level(tmp_path) -> None:
    exchange = FakeExchange()
    config = settings(tmp_path)
    first = GridBot(config, exchange)
    _, plan = first.plan()
    first._place(plan[0])

    restarted = GridBot(config, exchange)
    restarted.initialize()

    assert [item["price"] for item in exchange.placed].count("90") == 1
    assert restarted.state.initialized is True


def test_buy_replacement_deducts_base_coin_fee(tmp_path) -> None:
    exchange = FakeExchange()
    bot = GridBot(settings(tmp_path), exchange)
    bot.initialize()
    buy = bot.state.orders[0]
    exchange.updates[buy.order_id] = {
        "orderStatus": "Filled",
        "cumExecQty": buy.qty,
        "cumFeeDetail": {"BTC": "0.000001"},
    }
    exchange.market = Decimal("95")
    bot.reconcile()
    assert Decimal(exchange.placed[-1]["qty"]) == Decimal("0.110")
