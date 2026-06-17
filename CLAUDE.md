# Atlas

Multi-market equity research engine. One ticker in, a coherent research report out, told as a **story** a
portfolio manager follows in ten minutes. Atlas's job is to behave like the **same world-class analyst every
run** — judgment made explicit and **argued from evidence**, not asserted — so results are consistent,
replicable, and stress-testable.

> **⭐ Read `charter/CONTRACT.md` first, every run.** It is Atlas's constitution (v3.0) — the disciplines
> that make shallow, reflexively-conservative, hard-to-read analysis impossible by construction: *argue
> don't assert; the base is the honest most-likely with NO stacked bias; method fits the business; surface
> the crux; tell the story.* `METHODS.md` (the how) and the agent specs are subordinate to it.

> **Data policy:** Hermes (this project's data skill) freezes the facts first. For lake-cached
> filings, the `../_shared` Scout/Planner/Scripter agents still apply — read `../_shared/CLAUDE_SHARED.md`.

> **Data policy:** Hermes (this project's data skill) freezes the facts first. For lake-cached
> filings, the `../_shared` Scout/Planner/Scripter agents still apply — read `../_shared/CLAUDE_SHARED.md`.

## The four consistency pins (why Atlas doesn't swing run to run)
1. **Pinned analyst** — `charter/HOUSE_VIEW.md` + `METHODS.md` + `STYLE.md`. Boreas and Cassandra read them every run, so the analyst's priors don't drift.
2. **Frozen facts** — Hermes writes `output/<T>/<T>_databundle.json`; everyone reads that, never live data. Re-running against an old snapshot replays the old facts exactly.
3. **Prose from numbers + fixed slots** — load-bearing claims derive from the deterministic valuation and the schema's fixed sections, not free generation.
4. **Prior-run anchor** — each run diffs the previous report; every change must be justified in `change_log`.

On top of the pins: **conviction is measured.** Atlas re-runs the conclusion (rating + 3 thesis
pillars) three times on the frozen snapshot. Agree → HIGH; 2/3 → MEDIUM; split → LOW, and a split
forces either low-conviction mode (name the pivot) or an error/hallucination check. The invariant:
**same frozen facts + same charter → stable thesis and conclusion.** If they swing, that's a defect
signal, not noise.

## Agents (`.claude/agents/`) — v3, 8 agents (Metis dissolved into Daedalus)
| | Agent | Role (per `CONTRACT.md §9`) |
|---|---|---|
| A | **Atlas** | Orchestrator + synthesizer. Runs the pipeline, writes the **8-section story**, names the crux, makes the call. |
| T | **Theia** | **Landscape & evidence analyst.** Business + segments, industry, **named competitors & the share dynamic**, the addressable market, and the **SOURCED, ARGUED crux driver** (its base/bull/bear range). The evidence engine the valuation stands on. |
| G | **Pheme** | Market intelligence at freeze-time. The analyst tape, what's priced in, sentiment, the estimate-artifact check. Facts, not a vote. |
| D | **Daedalus** | **Valuation architect — owns the base** (absorbs the old Metis). Segment-first SOTP, method per segment, each its own WACC, the four levers argued, the **stacked-bias audit**, the exit-multiple math, the mandatory sensitivity, the four numbers, conviction, rating. |
| B | **Boreas** | Bull — the honest HIGHER reading of the crux, argued as **key debates** (not catalyst lists), each quantified. Blind, parallel. |
| C | **Cassandra** | Bear — the honest LOWER reading of the crux, **key debates** with named break-mechanisms. **Mandatory, blind, parallel.** |
| E | **Erinys** | Numeric auditor — verifies every figure, the exit-multiple math + T-invariance, and the bias-audit tally. |
| F | **Forseti** | Quality gate — enforces the **CONTRACT** (argued? unbiased? crux surfaced? method-fit? readable story?) + the numeric/consistency/completeness checks. Nothing ships without SHIP. |

## Pipeline (v3 — landscape & argument first, the call last; see `CONTRACT.md` §9 and METHODS.md "order of work")
1. **Freeze — Hermes ‖ Pheme ‖ Theia (parallel).** `python .claude/skills/hermes/us.py --ticker <T>` →
   `<T>_databundle.json`. **Pheme** freezes the market facts + the analyst tape + the estimate-artifact check.
   **Theia** maps the business & segments, the industry, the NAMED competitors & share dynamic, the addressable
   market, and **sources & argues the CRUX driver** (base/bull/bear range) → `<T>_crux.json` + `<T>_demand.json`
   + `<T>_industry.json`. All facts; none argues a call.
2. **Valuation — Daedalus (owns the base).** Segment-first SOTP (method per segment, **each its own WACC**); the
   **four levers argued** from Theia's evidence; the **honest base + the stacked-bias audit** (`bias_audit`); the
   exit-multiple math (`engine/exit_multiple_compute.py` via `sotp_compute.py`, with the T-invariance check); the
   **mandatory sensitivity** over the two levers the call hinges on; the street reconstruction; the four numbers,
   conviction, rating → `<T>_valuation.json`, then `python engine/assemble.py --ticker <T> --final-conviction
   <label> ...` → `<T>_headline.json`. **#1 fair value = the argued base; no weighted blend.**
3. **Debate — Boreas ‖ Cassandra (blind, parallel).** The **2–4 KEY DEBATES** anchored on the crux (NOT catalyst
   lists); each argued both ways and **quantified** ($/share worth); each ends in an `evidence_quality` grade.
   Bull = honest higher reading of the crux; bear = honest lower. Cassandra never sees Boreas.
4. **Synthesize `<T>.json`** per `schema/REPORT_SCHEMA.md` — the **8-section story** (the call → business →
   landscape → market → management → our valuation → the key debates → scenarios/conclusion), in `STYLE.md` voice.
   Name the crux in §1, resolve it in §7. The valuation overrides the narrative.
5. **Audit + gate — Erinys → Forseti.** Erinys verifies the figures + the exit-multiple math + the bias tally.
   Forseti enforces the **CONTRACT** (argued? unbiased? crux surfaced? method-fit? readable?) + the numeric gates.
6. **Render + ledger** — `voice_clean.py`, `render_pdf.py` + `render_excel.py`; then `reflect.py log`.

## Method selection (CONTRACT §2 — method fits the business)
Segment-first: split into real economic segments, pick the most EFFICIENT method per segment (high-growth →
**exit-multiple**; annuity → current earnings × multiple; cyclical → mid-cycle × through-cycle multiple; bank →
DDM; REIT/miner → NAV), **each segment its own WACC**. The registry in `METHODS.md` maps `business_type` → default,
stated with `method_why`. **Four numbers, each as value AND multiple**: (1) fair value today (the argued base),
(2) price, (3) fair value in 12m, (4) 12m target. Rating off implied 12m total return to #4: BUY ≥ +15%, SELL ≤
−10%, else HOLD; MoS widens at LOW conviction.

## Output (`output/<T>/`)
`<T>.json` (report) · `<T>_market_facts.json` + `<T>_industry.json` (Pheme: market facts incl. the
post-earnings analyst tape, and the business+industry overview) · `<T>_comps_inputs.json` + `<T>_comps.json`
(street reconstruction) · `<T>_inputs.json` (assumptions) · `<T>_valuation.json` (deterministic math) ·
`<T>_headline.json` (the four numbers + rating + conviction) · `<T>.pdf` (the read) · `<T>.xlsx` (the model,
with the Multiple Maths tab) · `<T>_databundle.json` (frozen facts, local only). Plus the cross-run
`runs/industry_log.jsonl` (Pheme appends one line per run; seeds a future industry tool).

## Publish (separate, JSON only)
`python deploy/push_to_intellidesk.py --ticker <T> --category US` — copies JSON (+ xlsx as a
download) to IntelliDesk, merges `categories.json`. The PDF stays local.

## Learning loop (record now, learn later)
`reflection` logs every call. Once calls resolve (`reflect.py resolve`), `reflect.py calibrate`
updates `charter/CALIBRATION.json` — mechanical, bounded, shows N, applied to future runs only.
**Priors in `HOUSE_VIEW.md` change only by human-approved versioned amendment.** Never auto-tune to P&L.
Grade decision quality (did the risk we *named* fire?), not luck.

## Markets
US is live (Hermes `us.py`). IN / VN / ID / TH are Hermes stubs — adding a market is one adapter to
`BUNDLE_SCHEMA.md`; the engine never changes. See `CAPABILITIES.md` for the registry rationale.

## Trial: AVGO
A frozen `output/AVGO/AVGO_databundle.json` already exists from the build smoke-test. To run a full
cycle: dispatch the Atlas agent on AVGO; it will reuse or refresh the bundle, run Boreas ‖ Cassandra,
Daedalus (AVGO is a `conglomerate` → SOTP), compute, gate, and render the five files.

> **Status (v2, 2026-06-16):** Valuation methodology reworked to v2 — comps + street reconstruction
> first (`engine/comps_implied.py`), scenario triples, the four numbers (`assemble.py`), the justified
> multiple + EPS→FCF bridge (`dcf_compute.py`), the Multiple Maths Excel tab, and Forseti gates for the
> reconstruction / numerator bridge / `target_12m` multiple. Engine chain smoke-tested end-to-end.
>
> **Status (v2.1, 2026-06-16):** Valuation CONTRACT tightened after the AVGO trial exposed a detached
> valuation. (1) The contested lever is argued across ALL THREE duality levers — growth, the **structural
> re-rate** (margin step-up + stickiness/scarcity → cyclicality → r), and risk — not growth alone; the
> numerator is a lever, not an SBC haircut. (2) Boreas and Cassandra each emit an explicit **numeric
> `scenario_spec`** so Daedalus **translates the panel's numbers**, never invents a generic fade; the **bull
> scenario must clear price** or say why not; every scenario reconciles to the comps grid; probabilities are
> the **conviction asymmetry** (HIGH 0.35 / MED 0.25 / LOW 0.15 tail, base = residual). (3) **Pheme** now also
> freezes a business+industry overview (`<T>_industry.json` + `runs/industry_log.jsonl`) and the
> post-earnings analyst TP/rating-change tape (`market_view`). Schema gains `market_view` + a richer
> `industry_position`. Engine label → **Atlas v2.1**. Files changed: `boreas.md`, `cassandra.md`,
> `daedalus.md`, `pheme.md`, `atlas.md`, `METHODS.md`, `REPORT_SCHEMA.md`, `push_to_intellidesk.py`.
>
> **Status (v2.2, 2026-06-16):** Scenario ARCHITECTURE reworked after the AVGO trial showed the base case was
> the swing between HOLD and SELL and was being pegged to the price (so it could never disagree with the market).
> New agent **Metis** owns the base case: the house's evidence-weighted, most-likely view (the variant
> perception) with an explicit one-sentence thesis and assumptions — never a neutral midpoint, never the
> consensus, never a reflexively-low traditional DCF (the house disciplines are inputs to judgment, not a
> guarantee of a low number). The four cases are now distinct: **consensus** (comps, a REFERENCE, unweighted),
> **base** (Metis), **bull** (Boreas = what must go right) and **bear** (Cassandra = what breaks) as deviations
> from the base on the key disputed variable. **Expected value** is weighted over base/bull/bear by each case's
> **own conviction, normalized by evidence quality** (HIGH 3 / MED 2 / LOW 1, weight = score/Σ — replaces
> base-as-residual). Pipeline order: Hermes ‖ Pheme → comps → **Metis** → Boreas ‖ Cassandra → Daedalus
> translates the three specs → gate → render. Files changed: new `metis.md`; `boreas.md`, `cassandra.md`,
> `daedalus.md`, `atlas.md`, `METHODS.md`, `REPORT_SCHEMA.md`, this file. Engine label → **Atlas v2.2**.
> Next: re-run AVGO through the v2.2 chain (Metis base → bull/bear deviations → translate → gate → render →
> publish to US-AI), then the other 9 US-AI names. v1 reports on IntelliDesk get replaced.
>
> **Status (v2.3, 2026-06-16):** Made the GROWTH lever and the data sourcing as rigorous as the valuation,
> after the AVGO trial showed growth was hand-waved and the numerator (tax/SBC) was grabbed. (1) New agent
> **Theia** (industry & demand) builds the growth from a **sourced demand curve**: `engine/demand_model.py`
> computes a year-by-year revenue path as an IDENTITY in sourced drivers (e.g. customer capex × content-share ×
> supplier-share) with an EARNED fade (logistic / capex-maturation, never a cliff) and a reduced-form
> reconciliation against a historical conversion-ratio band; `engine/connectors/edgar_capex.py` pulls the
> buyers' real capex from EDGAR XBRL (handles the tag inconsistencies). (2) **Pheme narrowed** to market intel;
> **FCF/tax components → Hermes** (`fcf_components` in the bundle); **consensus decomposition → Daedalus** (his
> comps step, fire #1 — he now fires twice). (3) **r = WACC** stated (CAPM build) in Metis/Daedalus, the same
> in the multiple decomposition and the DCF. (4) The multiple is argued ONLY as g/ROIC/r (no "won't pay for
> expansion" hand-wave); the numerator is built from sourced components and validated to the reported cash flow.
> (5) Excel gains a traceable **Demand (Theia)** tab. Pipeline: Hermes ‖ Pheme ‖ Theia → Daedalus#1 (comps +
> decomposition) → Metis (base, growth from Theia, WACC) → Boreas ‖ Cassandra → Daedalus#2 (integrate) → gate →
> render. New/changed: `theia.md`, `engine/demand_model.py`, `engine/connectors/edgar_capex.py`, `metis.md`,
> `daedalus.md`, `pheme.md`, `atlas.md`, `BUNDLE_SCHEMA.md`, `render_excel.py`, this file. Engine label → **Atlas v2.3**.
> Follow-ons: extend `us.py` to pull `fcf_components` structurally; `connectors/wsts.py` + `fred.py`; bring
> Erinys/Forseti to v2.3.
>
> **Status (v3.0, 2026-06-17):** FOUNDATION REWRITE after the AVGO session exposed that v2.x produced shallow,
> reflexively-conservative, hard-to-read analysis — the engine asserted numbers (a top-down demand cone, a muddled
> 10-yr DCF) instead of arguing them, stacked conservative choices into a false SELL on a fairly-valued name, buried
> the crux inside a "content share", and dumped 47 cards instead of telling a story. New **`charter/CONTRACT.md`**
> (v3.0) is now the constitution every agent reads first: **(§1) argue don't assert; the base is the honest
> most-likely with NO stacked bias** (the explicit `bias_audit` — 3+ same-direction leans = a bug); **(§2) method
> fits the business** — segment-first SOTP, the new **exit-multiple method** for high-growth (normalize → steady-state
> Gordon → discount at the **segment's own WACC**, `engine/exit_multiple_compute.py`), no more one-cone-one-DCF;
> **(§3) the four levers argued + a mandatory sensitivity**; **(§4) surface the crux** (the one variable that decides
> it); **(§5) bull/bear = 2–4 key debates, quantified, not laundry lists**; **(§6) the 8-section story arc.** Agents:
> **Metis dissolved into Daedalus** (the base IS the argued valuation, removing the hand-off where bias crept in);
> **Theia re-pointed** from "demand cone" to "source & argue the competitive share dynamics + the crux"; **Forseti
> gains CONTRACT gates**. Files: new `CONTRACT.md` + `exit_multiple_compute.py`; rewritten `METHODS.md`,
> `REPORT_SCHEMA.md`, `theia/daedalus/boreas/cassandra/atlas/forseti.md` (+ pheme/erinys aligned), `CLAUDE.md`;
> `sotp_compute.py` gains the ExitMultiple method; `metis.md` retired. Engine label → **Atlas v3**. Renderers +
> IntelliDesk page realign to the 8-section arc next; trial: re-run AVGO clean through v3 (the proof).
>
> **Status (v2.5, 2026-06-16):** Demand DISCIPLINE + the assumption ladder, after the AVGO v2.4 publication showed
> (a) the bull (and even the base) implied a physically-senseless end-market — the persistence bound needed ~$3.8T
> of ANNUAL hyperscaler AI capex by 2035 (~8x today), the base ~$3.0T, with nothing in the engine checking it; and
> (b) the reader could not see the assumptions behind each number ("show me what underpins the bull — I think it's
> made up"). Four changes: (1) **TAM/capex CEILING GATE** — `engine/demand_model.py` now computes each cone bound's
> IMPLIED primary driver (revenue ÷ content share = the spend pool the path requires) and reconciles it against a
> SOURCED `driver_ceiling` (the most bullish CREDIBLE third-party number), flagging `primary_driver_exceeds_sourced_ceiling`.
> Theia must supply the ceiling and EVERY bound (base included) must pass; a bound that breaches is an arithmetic
> error, not a thesis. (2) **`scenario_assumptions` — the per-case numbered LADDER** (REQUIRED): base/bull/bear each
> carry the explicit rows (revenue at FY+1/mid/terminal + decade CAGR, the implied-spend-pool-vs-ceiling row, content
> share, owner-FCF margin, r, terminal g, the non-contested segment, net debt, shares, implied value per share). Metis/
> Boreas/Cassandra author `assumption_rows`; Daedalus assembles the table and bounces any case that breaches the ceiling.
> (3) **Catalysts → 3-4 THEMATIC BUCKETS** (`{theme, horizon, what_to_watch, why_it_matters, bull_or_bear_tell}`), never
> a dated laundry list. (4) **Display fixes**: `synthesis_paths` carry `evidence_grade` not a 0%-rendering `prob`; the
> IntelliDesk valuation page renders SOTP (was DCF/DDM-only -> blank), the report page renders the assumption ladder +
> catalyst buckets. Files: `engine/demand_model.py`, `engine/render_pdf.py`, `engine/render_excel.py`, `theia.md`,
> `boreas.md`, `cassandra.md`, `metis.md`, `daedalus.md`, `atlas.md`, `REPORT_SCHEMA.md`, `METHODS.md`,
> `deploy/push_to_intellidesk.py`, IntelliDesk `page.tsx` + `valuation/page.tsx`. Engine label -> **Atlas v2.5**.
> Trial: re-run AVGO through the ceiling-gated cone (base/bull/bear all re-bounded), publish to US-AI.
>
> **Status (v2.4, 2026-06-16):** Scenario INTEGRATION reworked after the AVGO trial showed (a) the cases were
> dialing Theia's cone for a range that "felt right" rather than arguing a thesis, and (b) the
> conviction-weighted expected value manufactured a false point estimate that buried the thesis. Three changes:
> (1) **Thesis-first cases** — base/bull/bear each name the **specific product/customer/capex** that drives them
> and WHY (Boreas: which chip/socket and whose funded capex underpins the higher growth; Cassandra: which named
> in-sourcing/socket-loss/funding-limit invalidates the base). A range is not a thesis. (2) **The per-case
> conviction weighting is REMOVED** — Atlas no longer blends base/bull/bear into an expected value. Each analyst
> now grades **`evidence_quality`** (bull: CONTRACTED/EXTRAPOLATED/HOPED-FOR; bear: OBSERVABLE-AND-NEAR/MECHANISM/
> TAIL) instead of voting a conviction. (3) **Daedalus integrates differently**: **#1 fair value today = Metis's
> BASE** (the anchor); he builds a **`sensitivity_matrix`** around the base over the two levers the call hinges on,
> rolls the base forward to #3, and authors **#4 target = #3 leaned by a DOCUMENTED judgment** toward the
> better-evidenced side (a CONTRACTED bull or OBSERVABLE bear moves the target; a HOPED-FOR bull or TAIL bear is
> shown as the range but does not move the anchor). **Daedalus assigns the conviction** from that evidence read.
> Bull and bear `value_per_share` are reported AS-IS — the spread is the honest uncertainty, not a defect. Files
> changed: `daedalus.md`, `boreas.md`, `cassandra.md`, `metis.md`, `METHODS.md`, `REPORT_SCHEMA.md`,
> `engine/assemble.py` (#1 = base scenario; `--final-conviction`; sensitivity passthrough), this file. Engine
> label → **Atlas v2.4**. Trial: re-run AVGO through the v2.4 integration → publish to US-AI, then the other 9.
