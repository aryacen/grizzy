import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PATH = Path(__file__).resolve().parents[1] / "Backtest" / "grid_backtest.py"
SPEC = importlib.util.spec_from_file_location("grid_backtest", PATH)
grid = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = grid
SPEC.loader.exec_module(grid)


def candles(rows):
    return pd.DataFrame(
        rows,
        columns=["Open", "High", "Low", "Close"],
        index=pd.date_range("2026-01-01", periods=len(rows), freq="1min"),
    )


def test_buy_fill_creates_fee_adjusted_sell_replacement() -> None:
    data = candles([(100, 101, 89, 95)])
    sim = grid.GridSimulator(np.array([90.0, 100.0, 110.0]), 90.0, 0.001, 0.000001, 100.0)
    _, summary = sim.run(data)
    assert summary["buy_fills"] >= 1
    replacement = sim.active[1]
    assert replacement.side == "Sell"
    assert replacement.qty < 1.0
    assert sim.base > replacement.qty


def test_round_trip_earns_when_spacing_exceeds_fees() -> None:
    data = candles([(100, 100, 89, 95), (95, 101, 95, 100)])
    sim = grid.GridSimulator(np.array([90.0, 100.0, 110.0]), 90.0, 0.001, 0.000001, 100.0)
    initial = sim.cash + sim.base * data.iloc[0].Open
    equity, summary = sim.run(data)
    assert summary["fills"] >= 2
    assert equity.iloc[-1] > initial


def test_insufficient_explicit_balances_are_rejected() -> None:
    try:
        grid.GridSimulator(
            np.array([90.0, 100.0, 110.0]), 100.0, 0.001, 0.000001, 100.0,
            initial_quote=0.0, initial_base=0.0,
        )
        assert False, "expected balance validation"
    except ValueError as exc:
        assert "insufficient" in str(exc)


def test_capital_option_sizes_starting_portfolio() -> None:
    levels = np.linspace(60_000, 120_000, 101)
    quote_size = grid.size_quote_per_order(levels, 500, 0, 0.000001, 80_000)
    sim = grid.GridSimulator(levels, quote_size, 0, 0.000001, 80_000)
    starting_value = sim.cash + sim.base * 80_000
    assert 499 < starting_value <= 500


def test_requested_grid_is_the_cli_default() -> None:
    args = grid.build_parser().parse_args([])
    assert args.lower == 10_000
    assert args.upper == 120_000
    assert args.intervals == 184
    assert args.capital == 10_000
    assert args.fee_rate == 0.0002
