# `<TICKER>.json` — the report (Atlas v3)

The report is an **8-section STORY** (CONTRACT.md §6) that builds to "what are we buying into." Readable
prose, conclusion-first, no card-dump. Atlas writes it; Forseti gates it on the contract. Every number cites
a `<T>_databundle.json` field or Theia's sourced evidence; if a field is absent, omit it and record it in
`data_gaps` (never invent). Field names below are kept stable so the renderers (PDF + Vercel) and IntelliDesk
work unchanged; what changed is the ORDER (the 8-section arc) and that **`crux` and `key_debates` are now
load-bearing.**

## Identity
`ticker, name, listings, sector, industry, business_type (a METHODS.md key), currency, date, engine ("Atlas v3")`.

---

## § 1 — The call  (lead with the answer)
- `our_view` — 80–150 word TL;DR: the rating, conviction, the core reason, the single biggest risk. Deductive.
- `crux` — **NEW, load-bearing**: `{variable, one_line, base, bull, bear, what_decides_it}`. The ONE or TWO
  things that decide the call, stated in a sentence (CONTRACT §4). Surfaced here, resolved in §7.
- `recommendation` / `rating` — `{action, tone, current_price, target_12m, upside_pct, conviction, rationale, next_earnings}`.
- `four_numbers` / `valuation_headline` — the four numbers, each as value AND multiple: `fair_value_today`
  (#1 = the argued base, the anchor), `price_today`, `fair_value_12m` (#3, base rolled forward), `target_12m`
  (#4, #3 leaned by Daedalus's documented judgment). Plus `method_primary`, `method_why`, `band_low/high`,
  `target_reasoning`, and the return to #4 / #3 / the street. From `<T>_headline.json`.
- `thesis` — exactly 3 pillars `[{pillar, detail}]`, one idea each, claim first, tied to a number.

## § 2 — The business & its history  (what am I analyzing?)
- `business_overview` — `{summary, business_model, segments[{name, revenue_share_pct, growth_pct, margin_pct, nature, note}], customers[], geographic[]}`. `nature` ∈ growth / annuity / cyclical (drives the SOTP method).
- `historical_financials` — multi-year `[{fy, revenue_b, revenue_growth_pct, gross_margin_pct, ebitda_b, ebitda_margin_pct, net_income_b, fcf_b, eps}]`, **read as a TREND** (`historical_financials_read`), not a transcribed table.
- `snapshot` — 18–25 `{label, value}` metrics.

## § 3 — Industry, competition & peers  (the landscape + the opportunity)
- `industry_position` — `{market_overview, tam_usd_bn, tam_growth_pct, addressable_market, the_share_dynamic,
  revenue_drivers[], npat_margin_drivers[], product_differentiation, five_forces{}, moat, competitors[{name, position, share, trajectory}]}`. From Theia. **The share dynamic is the heart** — who takes share from whom, why, how fast, sourced.
- `peers` — `[{ticker, name, pe_ntm, ev_ebitda, rev_growth_ttm, ytd, y1, highlight?}]` + `peers_read` (one para).

## § 4 — Market view & runway  (what's priced in?)
- `market_view` — `{whats_priced_in (the reverse-multiple decomposition), street_view, post_earnings_analyst_actions[{date, firm, action, old_pt, new_pt, rating_change, note}], news_narrative, sentiment_narrative, runway, runway_verdict, market_lean}`. From Pheme.
- `street_reconstruction` — `{currency, what_price_implies, what_street_implies, history_anchor, our_justified_multiple, agree_disagree}`. Price + consensus decomposed into (g, ROIC, r); the precise agree/disagree. From Daedalus.

## § 5 — Management & capital allocation
- `management` — `{ceo, cfo, capital_allocation_history, recent_insider_activity[]}` (if in bundle).

## § 6 — Our valuation  (what we think, the argued math)
- `valuation_method` — the method chosen and WHY it fits this business (CONTRACT §2). For multi-segment: SOTP.
- `segment_valuation` — **the segment SOTP**: `[{name, nature, method (ExitMultiple/Multiple/DCF), revenue_path,
  margin, wacc, exit_multiple (if growth), implied_ev_b, implied_px, the four levers argued}]`. Each segment its own WACC.
- `four_levers` — for the value driver(s): `{growth_rate_and_duration, economics, wacc, exit_multiple}`, each ARGUED from Theia's evidence, with the source.
- `bias_audit` — **NEW, required (CONTRACT §1.3)**: `{rows:[{assumption, lean}], same_direction_count, verdict}`. The check that no 3+ assumptions lean the same way unargued.
- `earnings_bridge` — `{reported_eps → normalized_eps → owner_earnings_per_share → fcf_per_share}`, ties to year-1 FCF.
- `multiple_maths` — the duality block: `{current_multiple, justified_multiple, justified_grid[], duality_decomposition}`.

## § 7 — The key debates  (the 2–4 things that decide it)
- `key_debates` — **2–4** `[{debate, is_crux, bull_view, bear_view, our_verdict, what_would_change_our_mind, worth_per_share}]`. NOT a laundry list. Each argued both ways with our verdict and the $/share it's worth. The crux debate first. (Boreas ‖ Cassandra feed these; `bull_catalysts` / `bear_breakers` become supporting EVIDENCE inside a debate, not standalone laundry lists.)
- `bear_paragraph` — 150–250 word synthesized bear narrative.
- `key_risks` — ranked `[{rank, category, severity, likelihood, risk, monitor}]`.

## § 8 — Scenarios, sensitivity & conclusion
- `range_and_sensitivity` — `{anchor:"base = fair value today", cases:[{label, implied_value, thesis_one_line, evidence_grade, key_driver}], sensitivity_matrix:{axis_x, axis_y, grid[[..]], where_cases_land}, vs_price_pct}`. The base is #1; bull/bear are the range (no weighting). The sensitivity over the two levers the call hinges on. From `<T>_valuation.json`.
- `scenario_assumptions` — `{base, bull, bear}`, each `{label, one_line, implied_value, rows:[{driver, value, note}]}`, SAME row order across the three (revenue path, the crux variable, margin, WACC, exit multiple, implied px). The ladder the reader scans.
- `synthesis_paths` — 3 `[{label, outcome_range, description, evidence_grade}]` (prob is null in v3; carry evidence_grade).
- `catalysts_to_watch` — **3–4 thematic buckets** `[{theme, horizon, what_to_watch, why_it_matters, bull_or_bear_tell}]`, never a dated laundry list.
- `conclusion` — the risk/reward and the call in two sentences.

## Spine / housekeeping
- `conviction` — `{label, assigned_by:"daedalus", valuation_confidence, path_confidence, basis}`.
- `run_manifest`, `change_log` (diff vs prior run), `data_gaps`, `sources`.

---

Notes:
- `business_type` MUST be a METHODS.md key; Forseti checks the method matches and that the SOTP uses per-segment WACC.
- Sections render only if present, but Forseti's completeness + CONTRACT gates reject a missing crux, a missing bias_audit, a missing sensitivity, bull/bear as laundry lists, or any unargued assumption.
