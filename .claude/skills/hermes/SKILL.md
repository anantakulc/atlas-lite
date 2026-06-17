---
name: hermes
description: Fetch and freeze a market data bundle for a ticker — the frozen facts the Atlas engine reasons against. Use at the start of every Atlas research cycle. US is ready (yfinance + SEC EDGAR); other markets are stubbed to the same contract.
---

# Hermes — the data courier

Hermes fetches a ticker's facts once, normalizes them to a single schema, and freezes them to
`output/<T>/<T>_databundle.json` with a timestamp. Boreas, Cassandra, and Daedalus read that
frozen file, never live data. That is consistency pin #2: same frozen bundle → same facts →
same substance, and any run is replayable against its snapshot.

## Markets
| market | adapter | sources | status |
|---|---|---|---|
| US | `us.py` | yfinance + SEC EDGAR | **ready** |
| IN | `markets/in_.py` | screener.in + yfinance (.NS/.BO) | stub |
| VN | `markets/vn.py` | vnstock | stub |
| ID | `markets/id.py` | IDX portal + yfinance (.JK) + data lake | stub |
| TH | `markets/th.py` | Settrade Open API | stub |

## Run it (US)
```
python .claude/skills/hermes/us.py --ticker AVGO
```
writes `output/AVGO/AVGO_databundle.json`. Run from the Atlas project root (paths are cwd-relative).
Add `--no-sec` to skip the SEC EDGAR call when offline.

## Contract
Every adapter emits the identical shape in `BUNDLE_SCHEMA.md`. **Never invent a field**: if a
source doesn't provide it, omit it and record it under `_meta.gaps`. All money fields are in
`_meta.currency`, suffixed `_b` (billions) or `_m` (millions). Adding a market means writing one
adapter to this contract; the engine never changes. yfinance can rate-limit, so always check
`_meta.gaps` before trusting completeness.
