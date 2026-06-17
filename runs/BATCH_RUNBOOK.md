# AFK batch runbook — US-AI category

Self-contained procedure for one autonomous wake. Each wake processes **exactly one** pending ticker
from `runs/batch_queue.json` end-to-end, deploys it, then schedules the next wake. Fresh context each
time, so this file is the single source of truth. Working dir for engine steps: `Atlas/`.

## Per-iteration loop
1. Read `runs/batch_queue.json`. Pick the first ticker with `status: "pending"`. If none → the batch
   is complete; write a final note and **stop** (do not reschedule). Set that ticker `in_progress`.
2. Run the full Atlas cycle below for ticker `T`, category `US-AI`.
3. On success: set `status: "done"`. On failure that can't be fixed in one bounce: set `status:
   "failed"` with a one-line `error`, and DO NOT push a broken build. Either way, continue to step 4.
4. `ScheduleWakeup` (~120s) with this same batch prompt so the next ticker runs. Stop only when no
   pending remain.

## The cycle (v2 — mirrors Atlas/CLAUDE.md pipeline; comps first, model last)
- **A. Freeze facts — Hermes ‖ Pheme.** If `output/T/T_databundle.json` missing:
  `python .claude/skills/hermes/us.py --ticker T --out output/T/T_databundle.json`. Dispatch **Pheme**
  at the same time (market facts, NOT in the bull/bear panel): WebSearch the actual recent news, last
  earnings print + reaction, analyst rating/PT actions, capex/backlog datapoints, sentiment; **verify
  the feed's `eps_ntm`/`pe_ntm`** against live consensus (the artifact that hit every v1 name); write
  `market_view` + `runway_verdict` + `market_lean`. Never conclude from one headline.
- **B. Comps + market-implied layer (Daedalus).** Author `output/T/T_comps_inputs.json` (street currency
  per METHODS.md, fundamental `r`, street targets from Pheme, peers) and run
  `python engine/comps_implied.py --inputs output/T/T_comps_inputs.json --output output/T/T_comps.json`.
  Reconstruct the street: what the price implies, what the target implies, our justified multiple, the
  **contested lever**, and the precise agree/disagree.
- **C. Blind panel (ONE message, parallel).** Dispatch **Boreas** (bull) and **Cassandra** (bear —
  MANDATORY, never sees Boreas) on the contested lever + reconstruction. Each reads
  `charter/{HOUSE_VIEW,METHODS,STYLE}.md` + the bundle + the comps output, argues the lever, and returns
  a **`self_conviction`** (HIGH/MEDIUM/LOW) in its own case. For AI names: assess near-term runway
  explicitly even if a long-run correction is warranted.
- **D. Scenario-triple assumptions (Daedalus).** Author `output/T/T_inputs.json`: method by METHODS.md;
  10-year fade; explicit `fcf_b` per year; `earnings_bridge` (EPS→owner→FCF, must tie to year-1 FCF);
  `valuation_anchor`; `cross_check.inputs` complete. **Scenarios are (growth, ROIC/margin, discount)
  TRIPLES** — `key_changes` carries `stage1_growth`/`growth_path`, `terminal_g`, `wacc`, `roic`. NEVER a
  `fcf_multiplier`. Author the **gated `target_12m`** (defensible multiple × forward metric), justified
  against the intrinsic multiple. Beta shown raw + sanitized.
- **E. Compute** — `python engine/<method>_compute.py --inputs output/T/T_inputs.json --output
  output/T/T_valuation.json`; then `python engine/assemble.py --ticker T --bull-conviction <B>
  --bear-conviction <C> --data-quality <CLEAN|CORRECTED|POOR> --path-clarity <CLEAR|MIXED|UNCLEAR>
  --ensemble <E>` → the four numbers, rating, conviction.
- **F. Assemble `output/T/T.json`** per `schema/REPORT_SCHEMA.md`, `charter/STYLE.md` voice. The spine:
  `our_view`, `thesis` (3), `key_debate`, **`contested_levers`**, **`street_reconstruction`** (currency,
  what_price_implies, what_street_implies, history_anchor, our_justified_multiple, agree_disagree),
  `market_view` (Pheme), `conviction` (label + valuation_confidence + path_confidence), and the **four
  numbers** (`fair_value_today`, `price_today`, `fair_value_12m`=#3 intrinsic convergence,
  `target_12m`=#4 defensible — separate, gap named in `method_why`). Body: `snapshot`,
  `business_overview` (+ segments, customers), `historical_financials`, `bull_catalysts`,
  `bear_breakers`/`bear_paragraph`, `key_risks` (each with monitor), `peers`, **`multiple_maths`**,
  **`earnings_bridge`**, `dcf_scenarios` (triples), `catalysts_to_watch`, `data_gaps` (SOURCE via EDGAR —
  UA `Atlas Research algothinks@gmail.com`), `change_log` vs prior run.
- **G. Conviction + gate** — the level came from the panel asymmetry (assemble); also ensemble the
  conclusion 3x on the frozen snapshot for stability (split → name the pivot). Then
  `python engine/voice_clean.py --ticker T` and `python .claude/skills/scorecard/score.py --ticker T`.
  Forseti must see the street reconstruction, the numerator bridge, a justified `target_12m` multiple,
  and a two-axis conviction. REVISE → one targeted bounce, re-score.
- **H. Render** — `python engine/render_pdf.py --ticker T` and `python engine/render_excel.py
  --ticker T --category US-AI`. (If a prior file is locked, write to a temp name.)
- **I. Deploy** — `python deploy/push_to_intellidesk.py --ticker T --category US-AI`.
- **J. BUILD-VERIFY (gate before push)** — in `IntelliDesk/`, set dummy Supabase env
  (`NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co`, `NEXT_PUBLIC_SUPABASE_ANON_KEY=dummy`),
  `npm run build`. Require `EXIT 0` and that `/research/US-AI/T` prerenders. Fix the data shape (usually
  `to_web_payload`), never push red.
- **K. Push** — only if build green: `git add public/research && git commit && git push origin main`
  (redact any token). Mark ticker `done`.

## Standing rules
- Consistency pins hold: pinned charter, frozen facts, prose-from-numbers, prior-run diff.
- Plain register, one idea per sentence/bullet, deductive, **no em dashes**, no word caps.
- Be cautious on AI names: separate near-term runway from long-run valuation; source from analyst
  articles (Pheme's job), don't hand-wave.
- **Comps first, model last.** Reconstruct the street's argument before building a DCF; engage it, don't
  talk past it. The multiple is a compressed DCF — report value AND multiple together.
- Never hand-set a number to force a rating. #4 (the only judgement input) is gated: the defensible
  multiple must be justified against the intrinsic multiple. Rating falls out of implied 12m total return
  to #4 (BUY ≥ +15%, SELL ≤ −10%, else HOLD). Let the honest model land where it lands.
