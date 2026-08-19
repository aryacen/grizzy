from __future__ import annotations

import argparse
import logging
import sys

from .bot import GridBot
from .config import Settings
from .exchange import BybitExchange
from .state import BotState


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Safety-first Bybit spot grid bot")
    result.add_argument("command", choices=["plan", "check", "run", "status", "cancel"])
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parser().parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "status":
            state = BotState.load(settings.state_file, settings.symbol)
            counts: dict[str, int] = {}
            for order in state.orders:
                counts[order.status] = counts.get(order.status, 0) + 1
            print(f"symbol={settings.symbol} initialized={state.initialized} orders={len(state.orders)}")
            print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "No state yet")
            return
        exchange = BybitExchange(
            testnet=settings.testnet,
            api_key=settings.api_key,
            api_secret=settings.api_secret,
        )
        if args.command == "check":
            if not settings.api_key or not settings.api_secret:
                raise ValueError("Set BYBIT_API_KEY and BYBIT_API_SECRET first")
            exchange.check_auth()
            print(f"Authentication OK ({'testnet' if settings.testnet else 'MAINNET'})")
            return
        bot = GridBot(settings, exchange)
        if args.command == "plan":
            market, orders = bot.plan()
            print(f"{settings.symbol} market price: {market}")
            for order in orders:
                print(f"level={order.level:>3} {order.side:<4} price={order.price} qty={order.qty}")
            base_needed = sum((o.qty for o in orders if o.side == "Sell"), 0)
            quote_needed = sum((o.price * o.qty for o in orders if o.side == "Buy"), 0)
            print(f"Planned orders: {len(orders)} (no orders submitted)")
            print(
                f"Estimated starting balance needed: {base_needed} {bot.instrument.base_coin} "
                f"and {quote_needed} {bot.instrument.quote_coin}"
            )
        elif args.command == "run":
            if not settings.execute:
                raise ValueError("Refusing to submit orders: set GRID_EXECUTE=true after reviewing `gridbot plan`")
            bot.run()
        elif args.command == "cancel":
            if not settings.execute:
                raise ValueError("Cancellation requires GRID_EXECUTE=true")
            print(f"Cancellation requests submitted for {bot.cancel_owned()} bot-owned orders")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
