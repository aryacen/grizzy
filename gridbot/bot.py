from __future__ import annotations

import logging
import signal
import time
from decimal import Decimal

from .config import Settings
from .exchange import BybitExchange
from .models import PlannedOrder, TrackedOrder
from .state import BotState
from .strategy import decimal_text, floor_to_step, make_levels, make_plan

LOG = logging.getLogger(__name__)
ACTIVE = {"New", "PartiallyFilled", "Untriggered"}


class GridBot:
    def __init__(self, settings: Settings, exchange: BybitExchange) -> None:
        self.settings = settings
        self.exchange = exchange
        self.instrument = exchange.instrument(settings.symbol)
        self.levels = make_levels(
            settings.lower_price,
            settings.upper_price,
            settings.intervals,
            self.instrument.tick_size,
        )
        self.state = BotState.load(settings.state_file, settings.symbol)
        signature = "|".join(
            [
                settings.symbol,
                *[decimal_text(level) for level in self.levels],
                decimal_text(settings.quote_per_order),
            ]
        )
        if self.state.grid_signature and self.state.grid_signature != signature:
            raise ValueError(
                "Grid settings do not match the existing state file. Restore the old "
                "settings, or cancel its orders before using a new GRID_STATE_FILE."
            )
        self.state.grid_signature = signature
        self.stopping = False

    def plan(self) -> tuple[Decimal, list[PlannedOrder]]:
        market = self.exchange.last_price(self.settings.symbol)
        return market, make_plan(
            self.levels, market, self.settings.quote_per_order, self.instrument
        )

    def _next_link_id(self, side: str, level: int) -> str:
        self.state.sequence += 1
        stamp = int(time.time()) % 10_000_000
        return f"{self.settings.order_prefix}-{side[0].lower()}{level}-{stamp}-{self.state.sequence}"[:36]

    def _place(self, order: PlannedOrder) -> TrackedOrder:
        link_id = self._next_link_id(order.side, order.level)
        price = decimal_text(order.price)
        qty = decimal_text(order.qty)
        order_id, actual_link = self.exchange.place_limit(
            self.settings.symbol, order.side, qty, price, link_id
        )
        tracked = TrackedOrder(order_id, actual_link, order.level, order.side, price, qty)
        self.state.orders.append(tracked)
        self.state.save(self.settings.state_file)
        LOG.info("Placed %s %s at %s (level %s)", order.side, qty, price, order.level)
        return tracked

    def _preflight_balances(self, plan: list[PlannedOrder]) -> None:
        required_base = sum((o.qty for o in plan if o.side == "Sell"), Decimal("0"))
        required_quote = sum((o.price * o.qty for o in plan if o.side == "Buy"), Decimal("0"))
        balances = self.exchange.balances(
            [self.instrument.base_coin, self.instrument.quote_coin]
        )
        base = balances[self.instrument.base_coin]
        quote = balances[self.instrument.quote_coin]
        if base < required_base or quote < required_quote:
            raise ValueError(
                "Insufficient estimated available spot balance. "
                f"Need {required_base} {self.instrument.base_coin} and "
                f"{required_quote} {self.instrument.quote_coin}; "
                f"available approximately {base} and {quote}."
            )

    def initialize(self) -> None:
        if self.state.initialized:
            return
        market, plan = self.plan()
        if not self.settings.lower_price < market < self.settings.upper_price:
            raise ValueError(
                f"Market price {market} must be strictly inside the configured grid range"
            )
        self._preflight_balances(plan)
        LOG.info("Initializing %s orders around market price %s", len(plan), market)
        # A prior run may have stopped after placing only part of the initial grid.
        # Never duplicate a level already recorded in this state file.
        recorded_levels = {order.level for order in self.state.orders}
        for order in plan:
            if order.level in recorded_levels:
                LOG.info("Skipping already-recorded level %s", order.level)
                continue
            self._place(order)
            recorded_levels.add(order.level)
        self.state.initialized = True
        self.state.save(self.settings.state_file)

    def _active_levels(self) -> set[int]:
        return {o.level for o in self.state.orders if o.status in ACTIVE}

    def reconcile(self) -> None:
        updates = self.exchange.order_updates(self.settings.symbol)
        for order in self.state.orders:
            update = updates.get(order.order_id)
            if update:
                previous = order.status
                order.status = update.get("orderStatus", order.status)
                if order.status == "Filled" and not order.replacement_qty:
                    executed = Decimal(update.get("cumExecQty") or order.qty)
                    fees = update.get("cumFeeDetail") or {}
                    base_fee = Decimal("0")
                    if order.side == "Buy" and isinstance(fees, dict):
                        base_fee = Decimal(str(fees.get(self.instrument.base_coin, "0")))
                    order.replacement_qty = decimal_text(
                        floor_to_step(executed - base_fee, self.instrument.qty_step)
                    )
                if previous != order.status:
                    LOG.info("Order %s changed %s -> %s", order.link_id, previous, order.status)

        market = self.exchange.last_price(self.settings.symbol)
        active_levels = self._active_levels()
        for order in list(self.state.orders):
            if order.status != "Filled" or order.replacement_placed:
                continue
            target = order.level + 1 if order.side == "Buy" else order.level - 1
            if target < 0 or target >= len(self.levels) or target in active_levels:
                continue
            side = "Sell" if order.side == "Buy" else "Buy"
            price = self.levels[target]
            # Wait until PostOnly cannot immediately cross the book.
            if (side == "Sell" and price <= market) or (side == "Buy" and price >= market):
                continue
            qty = Decimal(order.replacement_qty or order.qty)
            if qty < self.instrument.min_qty:
                LOG.warning("Cannot replace %s: fee-adjusted qty %s is below minimum", order.link_id, qty)
                order.replacement_placed = True
                continue
            replacement = PlannedOrder(target, side, price, qty)
            self._place(replacement)
            order.replacement_placed = True
            active_levels.add(target)
        self.state.save(self.settings.state_file)

    def run(self) -> None:
        self.initialize()

        def stop(*_: object) -> None:
            self.stopping = True

        signal.signal(signal.SIGINT, stop)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, stop)
        LOG.info("Grid running; Ctrl+C stops monitoring but leaves orders open")
        while not self.stopping:
            try:
                self.reconcile()
            except Exception:
                LOG.exception("Polling error; retrying")
            time.sleep(self.settings.poll_seconds)
        LOG.info("Stopped monitoring; exchange orders were left open")

    def cancel_owned(self) -> int:
        updates = self.exchange.order_updates(self.settings.symbol)
        cancelled = 0
        for order in self.state.orders:
            status = updates.get(order.order_id, {}).get("orderStatus", order.status)
            if status in ACTIVE:
                self.exchange.cancel_order(self.settings.symbol, order.order_id)
                order.status = "Cancelled"
                cancelled += 1
        self.state.save(self.settings.state_file)
        return cancelled
