# Bybit spot grid bot

A small arithmetic grid bot that connects directly to Bybit V5 through Bybit's
official `pybit` client. It deliberately supports **spot only**: no margin, leverage,
perpetuals, or shorts.

## Safety model

- `plan` is read-only and uses public market data.
- Trading is disabled until `GRID_EXECUTE=true`.
- Testnet is the default.
- Mainnet additionally requires `GRID_MAINNET_CONFIRM=I_UNDERSTAND`.
- Orders use `PostOnly` and the bot cancels only order IDs recorded in its own state.
- Stopping the process leaves exchange orders open. Run `cancel` if you want them removed.
- API keys are read from `.env`, which is ignored by Git.

Use a dedicated Bybit subaccount/API key with only Spot Trade permission. Do not grant
withdrawal permission and, when practical, add an IP whitelist.

## Setup (PowerShell)

Python 3.10+ is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env`. Testnet and mainnet use different API keys. Configure a range that
contains the current price and choose the quote value allocated to each order.
Because this is unleveraged spot trading, the account must already hold enough base
coin for the planned sells and enough quote coin for the planned buys; `plan` prints
both estimates.

```powershell
python -m gridbot.cli plan
python -m gridbot.cli check
```

After reviewing the plan, set `GRID_EXECUTE=true`. On testnet:

```powershell
python -m gridbot.cli run
```

The bot places buys below the current price and sells above it. After a fill it waits
until the adjacent grid price is passive, then submits the opposite `PostOnly` order.
It keeps state in `.grid_state.json`, so restart with the same configuration and file.

Operational commands:

```powershell
python -m gridbot.cli status
python -m gridbot.cli cancel
pytest
```

`status` reports persisted local state. `cancel` checks Bybit and cancels active orders
owned by this bot. Do not edit grid parameters while a state file has live orders;
cancel first, then archive the old state file and start a new grid.

## Mainnet

Only after testing with testnet, set all three values:

```dotenv
BYBIT_TESTNET=false
GRID_EXECUTE=true
GRID_MAINNET_CONFIRM=I_UNDERSTAND
```

Grid trading can lose money in a sustained trend and fees can exceed the grid spread.
This software does not promise profit and is not financial advice.

## Backtesting

The historical one-minute dataset in `Backtest` can be tested with the separate
`Backtest/grid_backtest.py` engine. See `Backtest/GRID_BACKTEST.md` for parameters,
modeling assumptions, and generated reports.
