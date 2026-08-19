from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _decimal(name: str, default: str) -> Decimal:
    try:
        return Decimal(os.getenv(name, default))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    testnet: bool
    execute: bool
    mainnet_confirm: str
    symbol: str
    lower_price: Decimal
    upper_price: Decimal
    intervals: int
    quote_per_order: Decimal
    poll_seconds: float
    order_prefix: str
    state_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        settings = cls(
            api_key=os.getenv("BYBIT_API_KEY", "").strip(),
            api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
            testnet=_bool("BYBIT_TESTNET", True),
            execute=_bool("GRID_EXECUTE", False),
            mainnet_confirm=os.getenv("GRID_MAINNET_CONFIRM", "").strip(),
            symbol=os.getenv("GRID_SYMBOL", "BTCUSDT").strip().upper(),
            lower_price=_decimal("GRID_LOWER_PRICE", "90000"),
            upper_price=_decimal("GRID_UPPER_PRICE", "110000"),
            intervals=int(os.getenv("GRID_INTERVALS", "10")),
            quote_per_order=_decimal("GRID_QUOTE_PER_ORDER", "10"),
            poll_seconds=float(os.getenv("GRID_POLL_SECONDS", "5")),
            order_prefix=os.getenv("GRID_ORDER_PREFIX", "grid").strip(),
            state_file=Path(os.getenv("GRID_STATE_FILE", ".grid_state.json")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.symbol.isalnum():
            raise ValueError("GRID_SYMBOL must contain only letters and numbers")
        if self.lower_price <= 0 or self.upper_price <= self.lower_price:
            raise ValueError("Grid prices must satisfy 0 < lower < upper")
        if self.intervals < 2 or self.intervals > 100:
            raise ValueError("GRID_INTERVALS must be between 2 and 100")
        if self.quote_per_order <= 0:
            raise ValueError("GRID_QUOTE_PER_ORDER must be positive")
        if self.poll_seconds < 1 or self.poll_seconds > 60:
            raise ValueError("GRID_POLL_SECONDS must be between 1 and 60")
        if not self.order_prefix or len(self.order_prefix) > 12:
            raise ValueError("GRID_ORDER_PREFIX must be 1-12 characters")
        if self.execute and (not self.api_key or not self.api_secret):
            raise ValueError("BYBIT_API_KEY and BYBIT_API_SECRET are required to execute")
        if self.execute and not self.testnet and self.mainnet_confirm != "I_UNDERSTAND":
            raise ValueError(
                "Mainnet execution requires GRID_MAINNET_CONFIRM=I_UNDERSTAND"
            )
