# Valuation files (v2) — comps inputs, DCF inputs, the computed valuation

Four files, in pipeline order. **Daedalus authors the inputs** (assumptions + reasoning).
**Python computes** deterministically. Same inputs in → same numbers out, every run.

```
<T>_comps_inputs.json   ─comps_implied.py→  <T>_comps.json        (step 2: street reconstruction)
<T>_inputs.json         ─dcf_compute.py →   <T>_valuation.json    (step 5: price the scenarios)
                        ─assemble.py    →   <T>_headline.json     (the four numbers + rating + conviction)
```

The order matters: the **comps layer runs first** (a multiple is a compressed DCF; we decompress what
the price and the street target imply before modeling), then the panel argues the contested lever, then
the DCF prices the scenarios their arguments frame. See METHODS.md.

---

## 1. `<T>_comps_inputs.json` (Daedalus authors at step 2, from the bundle + Pheme's market facts)

```jsonc
{
  "ticker": "AVGO", "currency": "USD",
  "current_price": 389.31, "shares_outstanding_b": 4.758, "net_debt_b": 48.958,
  "fundamental_discount_rate": 0.097,   // r — BUSINESS risk, not a beta lifted off a rally. WACC for EV
                                         //     bases; cost of equity for P/E. Same r the DCF will use.
  "terminal_growth": 0.03, "horizon_years": 10,

  "anchor": {                            // the metric the multiple capitalizes — the industry's currency
    "type": "EV/FCF",                    // EV/FCF | EV/EBITDA | EV/Sales | P/E | P/B  (per METHODS.md row)
    "metric_label": "FCF (ttm)",
    "metric_value": 26.914,              // $b for EV bases; per-share for P/E, P/B
    "fcf_conversion": 1.0,               // FCF / anchor: 1.0 for EV/FCF; ~0.6 for EV/EBITDA;
                                         //   the steady FCF margin for EV/Sales; payout for P/E
    "roic": 0.30                         // for the duality decomposition (the payout lever)
  },

  "street": {                            // Pheme's frozen market facts — the consensus to reconstruct
    "target_mean": 522.06, "target_high": 650.0, "target_low": 300.0,
    "n_analysts": 45, "rating": "strong_buy",
    "thesis": "Custom AI silicon re-rates AVGO from cyclical chipmaker to structural AI compounder"
  },
  "history": { "anchor_cagr_5y": 0.18, "note": "FY22-25 FCF CAGR ~18%" },
  "peers": [ {"ticker": "NVDA", "multiple": 38.0}, {"ticker": "AMD", "multiple": 42.0} ],
  "contested_lever": "Durability of 20%+ FCF growth past the backlog; structural vs cyclical ROIC",

  "justified_g_grid": [0.10,0.12,0.15,0.18,0.20,0.22,0.25],   // optional; sensible defaults exist
  "roic_grid": [0.10,0.20,0.30,0.50], "duality_g_grid": [0.04,0.06,0.08]
}
```

### `<T>_comps.json` (comps_implied.py writes; deterministic)
Carries `current` and `street.{target_mean,target_high}` each as `{price, value_b, multiple,
implied_growth, implied_growth_pct}` — the growth each price implies in the anchor's currency. Plus
`justified_grid` (our multiple/price at a range of growth), `duality_decomposition` (the
`(1−g/ROIC)/(r−g)` table showing the ROIC/payout lever), `peer_median_multiple`, and a prose
`reconstruction` (`what_price_implies`, `what_street_implies`, `history_anchor`, `contested_lever`).

---

## 2. `<T>_inputs.json` (Daedalus authors at step 5, after the panel resolves the contested lever)

```jsonc
{
  "schema_version": "2.0", "ticker": "AVGO", "currency": "USD",
  "current_price": 389.31, "shares_outstanding_b": 4.758, "net_debt_b": 48.958,
  "dividend_per_share": 2.36,
  "business_type": "software",            // must match a METHODS.md key
  "sector_hint": "semiconductors",
  "base_fcf0": 26.914,                    // trailing FCF the scenario growth paths grow FROM

  "primary_method": {
    "name": "DCF",                        // DCF | DDM | SOTP | NAV (registry by business_type)
    "reasoning": "Why this method, citing METHODS.md.",
    "inputs": {
      "wacc": { "value": 0.097,
        "components": { "rf": 0.044, "beta": 1.15, "erp": 0.055,
                        "debt_weight": 0.03, "cost_of_debt_after_tax": 0.035 },
        "reasoning": "Ke = rf + beta x ERP. FUNDAMENTAL business risk — do not also crush the cash flows (no double-count)." },
      "terminal_growth": { "value": 0.03, "reasoning": "<= risk-free rate" },
      "forecast_horizon_years": 10,       // ~10y fade, not a 5y cliff (a short horizon prints falsely bearish)
      "fcf_projections": [ { "year": 2026, "fcf_b": 30.95, "rationale": "..." } /* base path, all years */ ]
    }
  },

  // The numerator bridge — so the P/E lens and the DCF lens use the SAME earnings (METHODS.md).
  "earnings_bridge": {
    "reported_eps": 4.77, "one_offs_per_share": 0.0, "sbc_per_share": -1.10,
    "normalized_eps": 3.67, "owner_earnings_per_share": 5.00, "fcf_per_share": 5.66,
    "notes": "SBC expensed as cash; no cyclical normalization needed for a structural grower"
    // engine adds fcf_b_from_bridge, year1_fcf_b, ties_to_year1 (must tie within 15%)
  },

  // The dual of the intrinsic value: the forward anchor the justified multiple is quoted on.
  "valuation_anchor": { "ev_metric_label": "NTM FCF", "ev_metric_value": 30.95, "eps_ntm": 7.80 },

  // #4 — the defensible 12m traded price: the multiple WE will defend x the 12m-forward metric.
  // This is the ONLY hand of judgement in the target, and Forseti gates it: the defensible_multiple
  // must be justified against the intrinsic-justified multiple and the reconstruction. A defensible
  // multiple far above what intrinsic supports, without an evidenced bull-lever resolution, is REVISE.
  "target_12m": {
    "basis": "EV/FCF", "forward_metric_label": "FY+1 FCF", "forward_metric_value": 33.0,
    "defensible_multiple": 45.0,
    "multiple_rationale": "Below today's 70x and the street's 94x; defends a premium to the 23.8x intrinsic only to the extent the backlog de-risks the next ~2 years of growth — names the gap, does not assume it persists."
  },

  "cross_check": {                        // peer multiple, always present (METHODS.md)
    "name": "Peer EV/FCF", "reasoning": "...",
    "inputs": { "multiple_type": "EV/EBITDA", "peer_median_multiple": 40.0, "fy_estimate": 30.95 }
    // multiple_type: EV/EBITDA | EV/Sales | EV/FCF | P/E | P/B. fy_estimate is the metric it applies to.
  },

  // Scenarios as (growth, ROIC/margin, discount) TRIPLES — the operating story flexes, not just WACC.
  "scenarios": [
    { "label": "Bear", "probability": 0.30, "probability_reasoning": "...",
      "key_changes": { "stage1_growth": 0.08, "terminal_g": 0.025, "wacc": 0.105, "roic": 0.20 },
      "reasoning": "AI capex digests; growth fades fast and ROIC normalizes toward the old cycle" },
    { "label": "Base", "probability": 0.45, "probability_reasoning": "...",
      "key_changes": { "stage1_growth": 0.15, "terminal_g": 0.03, "wacc": 0.097, "roic": 0.30 },
      "reasoning": "Backlog holds the next 2-3y; growth glides to terminal" },
    { "label": "Bull", "probability": 0.25, "probability_reasoning": "...",
      "key_changes": { "stage1_growth": 0.22, "terminal_g": 0.035, "wacc": 0.09, "roic": 0.40 },
      "reasoning": "Hyperscaler capex persists; structural ROIC sustains high growth" }
  ]
  // The engine derives each scenario's FCF path from base_fcf0 along a stage1_growth->terminal fade
  // (or an explicit growth_path). Probabilities are DEFENDED, not 30/45/25 by habit.
}
```

`stage1_growth` (+ optional `fade_start_year`, default 3) builds a faded path; or pass an explicit
`growth_path` (a list, one growth rate per year); or, only if genuinely needed, an explicit
`fcf_projections` override. **Never** a blanket `fcf_multiplier` to force a scenario to a target.

For `business_type: bank`, `primary_method.name = "DDM"`, the anchor is **P/B ↔ ROE** (no FCF bridge),
and the comps currency is justified P/B. For `conglomerate`, `name = "SOTP"` with a `segments` array.

### `<T>_valuation.json` (dcf_compute.py writes; deterministic)
As v1 (`primary_method.outputs`, `sensitivity`, `cross_check`, `scenarios`, `blended_target`,
`upside_pct`) **plus**:
- `justified_multiple` — `{ev_metric_label, ev_metric_value, justified_ev_multiple, current_ev_multiple,
  eps_ntm, justified_pe_ntm, current_pe_ntm}`. The base-case value expressed as a multiple, beside the
  current multiple — value and multiple always reported together.
- `earnings_bridge` — the authored bridge, with the engine's `fcf_b_from_bridge`, `year1_fcf_b`,
  `ties_to_year1` tie-out.
- each scenario now carries `derived_growth_path` and a `levers` triple `{stage1_growth, terminal_g,
  wacc, roic, ebit_margin}`.

---

## 3. The four numbers (`assemble.py` → `<T>_headline.json`)

`assemble.py` computes the four numbers, the rating, and the conviction synthesis. Each value is
reported WITH its multiple (the dual).

| | Number | Formula |
|---|---|---|
| 1 | `fair_value_today` | probability-weighted scenario implied_px (intrinsic) + `justified_multiple` |
| 2 | `price_today` | market + `current` multiple |
| 3 | `fair_value_12m` | `#1 × (1 + r) − dividend` — pure convergence to intrinsic |
| 4 | `target_12m` | `defensible_multiple × forward_metric` (bridged to price) — where WE think it trades |

`#3` and `#4` are SEPARATE on purpose. `#4 − #3` is the part of the call that rests on the market
keeping a premium; the headline names it and never bridges it with a persistence fudge. **The rating is
off `#4`**, and the headline also shows the return to `#3` (`convergence_return_pct`) and to the street
mean (`street_return_pct`) so the reader sees how much rests on the market. If no `target_12m` block is
authored, `#4` falls back to `#3` (we default to assuming convergence, never to a generous multiple).

Rating: BUY ≥ +15%, SELL ≤ −10%, else HOLD; MOS widens at LOW conviction.

### Conviction (measured, two axes)
`assemble.py` flags: `--bull-conviction`, `--bear-conviction` (the panel's self-conviction),
`--ensemble` (3x-rerun stability), `--data-quality`, `--path-clarity`. It derives:
- `label` from the **asymmetry** (strong winning case vs weak opposition → HIGH; two strong opposed
  cases → earned MEDIUM; weak winning case → LOW), then capped by a wide band, a corrected data
  artifact, or an ensemble split.
- `valuation_confidence` (band width + data quality) and `path_confidence` (catalyst clarity, knocked
  down when `#4` leans on a re-rate above intrinsic) — reported separately so a flat label stops hiding
  the truth.
