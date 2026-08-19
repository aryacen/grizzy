from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import TrackedOrder


@dataclass
class BotState:
    symbol: str
    grid_signature: str = ""
    initialized: bool = False
    sequence: int = 0
    orders: list[TrackedOrder] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path, symbol: str) -> "BotState":
        if not path.exists():
            return cls(symbol=symbol)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw["symbol"] != symbol:
            raise ValueError(
                f"State belongs to {raw['symbol']}, not {symbol}. Use a different GRID_STATE_FILE."
            )
        raw["orders"] = [TrackedOrder.from_dict(item) for item in raw.get("orders", [])]
        return cls(**raw)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "symbol": self.symbol,
            "grid_signature": self.grid_signature,
            "initialized": self.initialized,
            "sequence": self.sequence,
            "orders": [order.to_dict() for order in self.orders],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)
