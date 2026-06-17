# `<TICKER>_databundle.json` — the frozen facts (what Hermes delivers)

Hermes fetches once, normalizes to this shape, and freezes it with a timestamp. Boreas,
Cassandra, and Daedalus reason against **this file**, not live data. That is consistency pin
#2: same frozen bundle + same charter → same substance. Re-running against an old bundle
replays the old facts exactly.

Every market adapter (`us.py`, `markets/in.py`, ...) emits this identical schema, so the
engine is market-agnostic. Numbers carry their reporting currency; `_meta.currency` names it.

**`fcf_components` (required, v2.3) — the sourced lines the valuation builds owner-FCF FROM** (so it models,
never grabs): `revenue`, `ebit`, `intangible_amortization` (the non-cash purchase-accounting add-back, SEPARATE
from `depreciation`), `pretax`, `gaap_tax_provision` + rate, **`cash_taxes_paid` + `cash_tax_rate`** (the real
rate — the GAAP rate can go negative on reserve releases), `deferred_taxes`, `wc_change`, `sbc`, `capex`,
**`open_market_buyback` vs `tax_withholding_repurchase`** (only the former offsets SBC dilution), `dividends`,
`diluted_shares`, and `forward_tax_guidance` (Pillar Two / holiday roll-off). From the 10-K/10-Q via EDGAR XBRL
(cash-flow + tax note), every figure to a named filing line. *(Engineering follow-on: extend `us.py` to pull
these structurally, mirroring `engine/connectors/edgar_capex.py`'s XBRL fallback-chain; until then they are
sourced by a filing read and frozen here.)*

```jsonc
{
  "_meta": {
    "ticker": "AVGO",
    "snapshot_id": "AVGO_2026-06-15T0900Z",
    "as_of_utc": "2026-06-15T09:00:00Z",
    "market": "US",
    "currency": "USD",
    "adapter": "hermes/us",
    "sources": [
      { "name": "yfinance", "fetched_utc": "2026-06-15T09:00:01Z" },
      { "name": "SEC EDGAR", "fetched_utc": "2026-06-15T09:00:03Z", "cik": "0001730168" }
    ],
    "gaps": ["segment-level capex not in structured data"]   // what couldn't be fetched
  },

  "profile": {
    "name": "Broadcom Inc.", "listings": "NASDAQ", "sector": "Technology",
    "industry": "Semiconductors", "country": "US",
    "description": "…", "employees": 37000,
    "business_type_hint": "conglomerate"   // Hermes' guess; Daedalus confirms vs METHODS.md
  },

  "price": {
    "current": 285.0, "currency": "USD", "asof": "2026-06-13",
    "high_52w": 312.0, "low_52w": 138.0, "ma50": 270.0, "ma200": 220.0,
    "ytd_pct": 18.0, "return_1y_pct": 92.0, "beta": 1.15
  },

  "market_stats": {
    "market_cap_b": 1339.0, "enterprise_value_b": 1386.0,
    "shares_outstanding_b": 4.7, "net_debt_b": 47.0,
    "adtv_usd_m": 4200.0, "dividend_per_share": 2.36, "dividend_yield_pct": 0.83
  },

  "valuation_multiples": {              // trailing + forward where available
    "pe_ttm": 38.0, "pe_ntm": 30.0, "ev_ebitda_ttm": 28.0, "ev_ebitda_ntm": 22.0,
    "ev_sales_ntm": 18.0, "pb": 12.0, "fcf_yield_pct": 1.6, "peg": 1.4
  },

  "financials": {                       // annual, most-recent-first; up to ~6 years
    "income": [
      { "fy": "FY24", "revenue_b": 51.6, "gross_profit_b": 32.5, "ebit_b": 23.5,
        "ebitda_b": 26.0, "net_income_b": 14.0, "eps": 3.0, "shares_b": 4.7 }
    ],
    "balance": [
      { "fy": "FY24", "cash_b": 9.3, "total_debt_b": 66.0, "total_equity_b": 68.0, "total_assets_b": 168.0 }
    ],
    "cashflow": [
      { "fy": "FY24", "cfo_b": 20.0, "capex_b": 0.5, "fcf_b": 19.5, "dividends_paid_b": 9.8, "buybacks_b": 5.0 }
    ]
  },

  "estimates": {                        // street consensus if available (yfinance / analyst)
    "revenue_ntm_b": 67.0, "eps_ntm": 7.8, "target_mean": 320.0, "target_median": 315.0,
    "num_analysts": 38, "rec_mean": 1.8
  },

  "peers": [                            // for the relative cross-check
    { "ticker": "NVDA", "name": "NVIDIA", "pe_ntm": 34.0, "ev_ebitda_ntm": 30.0, "rev_growth_ttm_pct": 60.0 }
  ],

  "segments": [                         // if disclosed; drives SOTP eligibility
    { "name": "Semiconductor solutions", "revenue_b": 30.0, "ebit_margin_pct": 50.0 },
    { "name": "Infrastructure software", "revenue_b": 21.6, "ebit_margin_pct": 60.0 }
  ],

  "filings": [                          // SEC EDGAR pointers (US); other markets: local portal
    { "type": "10-Q", "period": "Q2 FY26", "filed": "2026-06-05", "url": "https://www.sec.gov/..." }
  ]
}
```

Rules:
- **Never invent a field.** If a source doesn't provide it, omit it and record it in `_meta.gaps`.
- All money fields are in `_meta.currency`, suffixed `_b` for billions or `_m` for millions.
- `snapshot_id` is `"<TICKER>_<as_of compact>"`; it is echoed into `<T>.json → run_manifest.snapshot_id`.
