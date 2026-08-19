from __future__ import annotations

from decimal import Decimal
from typing import Any

from pybit.unified_trading import HTTP

from .models import Instrument


class BybitExchange:
    def __init__(self, *, testnet: bool, api_key: str = "", api_secret: str = "") -> None:
        args: dict[str, Any] = {"testnet": testnet}
        if api_key and api_secret:
            args.update(api_key=api_key, api_secret=api_secret)
        self.session = HTTP(**args)

    @staticmethod
    def _result(response: dict) -> dict:
        if response.get("retCode") != 0:
            raise RuntimeError(f"Bybit error {response.get('retCode')}: {response.get('retMsg')}")
        return response["result"]

    def instrument(self, symbol: str) -> Instrument:
        result = self._result(
            self.session.get_instruments_info(category="spot", symbol=symbol)
        )
        items = result.get("list", [])
        if not items:
            raise ValueError(f"Unknown or unavailable spot symbol: {symbol}")
        item = items[0]
        price_filter = item["priceFilter"]
        lot = item["lotSizeFilter"]
        return Instrument(
            symbol=item["symbol"],
            base_coin=item["baseCoin"],
            quote_coin=item["quoteCoin"],
            tick_size=Decimal(price_filter["tickSize"]),
            qty_step=Decimal(lot["basePrecision"]),
            min_qty=Decimal(lot["minOrderQty"]),
            max_qty=Decimal(lot.get("maxLimitOrderQty", "0")),
            min_amount=Decimal(lot["minOrderAmt"]),
        )

    def last_price(self, symbol: str) -> Decimal:
        result = self._result(self.session.get_tickers(category="spot", symbol=symbol))
        return Decimal(result["list"][0]["lastPrice"])

    def balances(self, coins: list[str]) -> dict[str, Decimal]:
        result = self._result(
            self.session.get_wallet_balance(accountType="UNIFIED", coin=",".join(coins))
        )
        found: dict[str, Decimal] = {coin: Decimal("0") for coin in coins}
        for account in result.get("list", []):
            for entry in account.get("coin", []):
                # A conservative cash estimate for non-margin spot orders.
                available = (
                    Decimal(entry.get("walletBalance") or "0")
                    - Decimal(entry.get("locked") or "0")
                    - Decimal(entry.get("spotBorrow") or "0")
                )
                found[entry["coin"]] = max(Decimal("0"), available)
        return found

    def place_limit(self, symbol: str, side: str, qty: str, price: str, link_id: str) -> tuple[str, str]:
        result = self._result(
            self.session.place_order(
                category="spot",
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=qty,
                price=price,
                timeInForce="PostOnly",
                orderLinkId=link_id,
                isLeverage=0,
                orderFilter="Order",
            )
        )
        return result["orderId"], result.get("orderLinkId", link_id)

    def order_updates(self, symbol: str) -> dict[str, dict]:
        active = self._result(
            self.session.get_open_orders(category="spot", symbol=symbol, limit=50)
        ).get("list", [])
        history = self._result(
            self.session.get_order_history(category="spot", symbol=symbol, limit=50)
        ).get("list", [])
        return {item["orderId"]: item for item in [*history, *active]}

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self._result(
            self.session.cancel_order(category="spot", symbol=symbol, orderId=order_id)
        )

    def check_auth(self) -> None:
        self._result(self.session.get_wallet_balance(accountType="UNIFIED"))

