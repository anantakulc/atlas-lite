# Atlas method mechanics (v3)

> Subordinate to **`charter/CONTRACT.md`** — that holds the *why* and the discipline; this holds the
> *how*. Where they ever conflict, the contract wins. The job of this file is to make the method
> **fit the business** (CONTRACT §2) and the four levers **argued and sensitized** (CONTRACT §3).

---

## Order of work (v3 — landscape and argument first, the call last)

A real analyst does not model cold. They learn the business, map the competition, find the one or two
variables that decide it, argue those from evidence, *then* value. Atlas works the same way.

1. **Freeze the facts — Hermes ‖ Pheme ‖ Theia (parallel).** Hermes freezes the quantitative bundle
   (financials, price, multiples, peers, `fcf_components`). **Pheme** freezes the market bundle (latest
   results + reaction, the analyst tape, consensus, sentiment; verifies estimate fields). **Theia** maps
   the business, the industry, the **named competitors and the share dynamic**, the **addressable market**,
   and — most important — **sources and argues the crux driver** (e.g. custom-vs-merchant silicon share,
   wallet share of capex), handing a reasoned central estimate + range for each. All facts; none argues a call.
2. **Build the argued valuation — Daedalus (the core).** Segment-first SOTP (below). For each segment,
   pick the most efficient method (registry), argue the **four levers** from Theia's evidence, build the
   **honest base** (audited for stacked bias, CONTRACT §1.3), and run the **mandatory sensitivity**. The
   base IS the argued valuation — there is no separate base agent.
3. **Debate the crux — Boreas (bull) ‖ Cassandra (bear), blind & parallel.** The **2–4 key debates**
   (CONTRACT §5), each argued both ways, anchored on the crux. Bull/bear are the honest higher/lower
   readings of the crux variable, each naming what it is worth.
4. **Synthesize the story — Atlas.** The 8-section report (CONTRACT §6), crux named, prose readable.
5. **Audit + gate — Erinys → Forseti.** Numbers tie; the contract checks pass; ship.

There is **no probability-weighted expected value**. #1 fair value = the argued base; bull and bear are
the honest range, each its own thesis. The width of the range is the honest measure of the uncertainty.

---

## Segment-first SOTP (the default structure for any multi-segment name)

Decompose the company into its real economic segments and value each on its own terms (CONTRACT §2.1).
A high-growth engine, a mature annuity, and a cyclical line do **not** share a growth path, a margin, a
risk, or a multiple — never blend them into one cone and one number. For each segment state: revenue
path, margin/economics, **its own WACC** (CONTRACT §2.3), and the method below. Sum the segment EVs,
less net debt, ÷ shares.

### Method per segment — pick the most efficient (least-distorting)

| Segment nature | Method | Why |
|---|---|---|
| **High-growth** | **Exit-multiple** (spec below) | isolates the only real question — *how big do earnings get* — and avoids the g>r blow-up and the ROIC-muddle of a forced perpetual formula |
| **Mature / annuity** | current (near-term) earnings × justified multiple | it is already at steady state; the multiple capitalizes it directly |
| **Cyclical** | normalized **mid-cycle** earnings × through-cycle multiple | never capitalize peak or trough |
| **Whole-company** (single-segment) | the registry engine below | DCF / DDM / NAV as the business dictates |

### The EXIT-MULTIPLE method (the clean way to value growth — CONTRACT §2.2)

The high-growth method, because a 10-year explicit DCF muddles the ramp into ROIC and r, and a
single-stage Gordon blows up when g > r. Instead:

1. **Build earnings to a normalization year T** (when growth has matured to a steady ~single-digit
   rate — typically 4–6 years out). Earnings_T from the argued revenue × margin (per segment).
2. **Apply a well-behaved steady-state multiple at T.** In steady state g < r, so the single-stage
   Gordon is valid and hand-checkable:  `exit P/E = (1 − g_LT / ROIC) / (r − g_LT)`. The exit multiple
   is an *argued output* of the long-run growth, ROIC, and the segment r — not a number picked. Quote
   it and reconcile it to where mature comparables trade.
3. **Discount back at the segment WACC:**  `value today = Earnings_T × exit-multiple ÷ (1 + r)^T`.
   The method is **robust to the choice of T** (the answer barely moves whether you normalize at 2029
   or 2033 — verify this; a large T-sensitivity means the exit multiple and the growth path disagree).
4. Add the interim FCF thrown off years 1→T if material (small for a heavy-reinvestor, larger for a
   high-payout name); a pure exit-multiple slightly understates by ignoring it — say so.

`engine/exit_multiple_compute.py` does this deterministically.

---

## Registry — primary engine and the street's currency (whole-company / per-segment)

| `business_type` | Primary engine | Street currency / duality | Driver lens |
|---|---|---|---|
| `bank` | Multi-stage DDM + excess-return | **P/B ↔ ROE**: justified P/B = (ROE−g)/(Ke−g) | DuPont, NIM, credit cost |
| `insurer` | Excess-return / embedded value | P/B ↔ ROE, P/EV | combined ratio, investment yield |
| `asset_manager` | DCF (FCFE) | P/E, P/AUM ↔ fee × AUM growth | net flows, fee rate |
| `reit` | NAV + AFFO | P/AFFO, cap rate ↔ NOI | NOI, occupancy, cap rate |
| `miner_ep` | NAV of reserves | EV/EBITDA at a **mid-cycle deck** | deck, AISC, reserve life |
| `software` | DCF (FCFF) or exit-multiple if hypergrowth | **P/E and EV/FCF on SBC-adj owner earnings**, Rule-of-40 | NRR, gross margin, SBC |
| `industrial` | DCF (FCFF) | P/E and EV/EBITDA ↔ (g, ROIC, r) | backlog, capex cycle |
| `consumer` | DCF (FCFF) | P/E, EV/EBITDAR | same-store sales |
| `telecom_utility` | DCF / DDM if regulated | EV/EBITDA, yield, P/B↔ROE | rate base, allowed ROE |
| `highgrowth_preprofit` | Scenario DCF / exit-multiple | EV/Sales ↔ out-year margin × growth | TAM, durability, path to FCF |
| `cyclical` | **Normalized** DCF or EV/EBITDA | through-cycle multiple on **normalized** EPS | cycle position |
| `conglomerate` | **SOTP** — each segment by its own row + method + WACC | blended/segment multiples | segment mix |

The registry is a default, not a straitjacket (CONTRACT §2.2): the analyst states why the method fits
*this* business in `method_why`. A multi-segment growth name (AVGO) → SOTP with the AI segment on the
exit-multiple, software as an annuity multiple, non-AI as a cyclical multiple — three methods, three WACCs.

---

## The four levers — state, argue, sensitize (CONTRACT §3)

Every value reduces to four levers. Name each, argue each from Theia's evidence, then sensitize:
1. **Growth = rate × DURATION** — for a fast-grower, duration (how many years the ramp lasts) is usually
   the bigger swing, and the post-ramp durability is the contested part.
2. **Economics** — margin and cash conversion → owner-FCF (the numerator bridge below).
3. **r** — the segment WACC, CAPM-built, fundamental beta, shown.
4. **Exit / terminal multiple** — `(1 − g_LT/ROIC)/(r − g_LT)`, reconciled to mature comps.

A **sensitivity table over these four is mandatory** — the call's fragility *is* the finding. Name the
dominant lever; for high-multiple names it is usually **r and growth-duration**, with **ROIC second-order**
(do not agonize over the lever that doesn't move the answer).

---

## The numerator — build owner-FCF from sourced components, never grab it

P/E uses accounting EPS; intrinsic value uses cash. Bridge them every time, and **validate the build ties
to the reported cash-flow statement in the base year before projecting:**
```
Revenue → cash EBIT (GAAP EBIT + acquisition-intangible amortization, a non-cash purchase-accounting charge)
        → − CASH taxes (cash-taxes-PAID rate, NOT the GAAP provision — GAAP can be near-zero from reserve
          releases and is useless forward; carry a forward rise only where the filing sources it, e.g. Pillar Two)
        → + maintenance D&A − capex − ΔWC (normalize a ramp-year working-capital build) → FCFF
        → − SBC (net of OPEN-MARKET buyback) → owner FCF
```
**SBC — charge the cost ONCE.** Its economic hit is dilution; open-market buybacks offset it. Either
expense SBC and hold shares flat (the buyback maintaining the count), OR keep SBC in FCF and grow shares
by NET dilution — never both, never neither. Tax-withholding-on-vesting repurchases are comp cost, not
capital return — they are NOT the offset (a name can report a big "repurchase" line that is mostly
withholding). Material for software/semis; immaterial elsewhere.

---

## The street reconstruction — what's priced in (Pheme + Daedalus)

Decompose the price and the consensus target into what they require, and engage it: `target = street EPS
× street multiple`; decompose that multiple into the **(g, ROIC, r)** — or implied ROE for a bank — it
needs. A multiple is NOTHING but g, the numerator/ROIC, and r; there is no separate "multiple expansion"
to pay for or refuse. State the street's thesis in one line, test each lever against the frozen facts,
and mark the **precise** point of agreement and disagreement. We engage the street's argument; we never
produce a rival number and shrug.

---

## The four numbers (each as value AND multiple)

| | Number | How |
|---|---|---|
| 1 | **Fair value today** | the **argued base** (the segment SOTP) + its justified multiple. NOT a weighted blend. |
| 2 | **Price today** | market + current multiple |
| 3 | **Fair value in 12m** | #1 rolled forward at the fundamental r, less the forward dividend/buyback yield |
| 4 | **Target in 12m** | #3 adjusted by a **documented judgment** off the sensitivity + the evidence read across bull/bear, shown beside the street's target |

#3 and #4 are different and the gap is named (which case's evidence moved the target, by how much) — never
a persistence fudge. The base is #1; bull and bear are the range, not weights.

---

## Conviction — measured by evidence quality (Daedalus sets it)

Graded by the WEAKEST necessary link in the base and the two deviations:
- **HIGH** — base rests on contracted/observed/mechanically-forced facts (signed backlog/RPO, current
  run-rate, an accounting identity); the bull-bear spread is tight.
- **MEDIUM** — base is a reasonable extrapolation of an established trend, with named support.
- **LOW** — the call hinges on a genuinely UNKNOWABLE variable (a multi-year platform bet, an unproven
  ROI); the range is WIDE and the margin of safety widens. A wide range on a true unknown is the honest
  output, not a defect. Report two axes: **valuation confidence** (band width, data quality) and **path
  confidence** (how much rests on the market continuing to pay).

---

## Rating

Off implied 12-month total return to **our** target (#4) vs price: **BUY ≥ +15%, SELL ≤ −10%, HOLD
between.** MoS widens at LOW conviction. Show the return to #3 (pure convergence) and to the street's
target, so the reader sees how much rests on the market.

---

## Compute scripts
- **Exit-multiple** (growth segments): `engine/exit_multiple_compute.py` — normalize → steady-state Gordon → discount at segment r.
- **SOTP** (the wrapper): `engine/sotp_compute.py` — per-segment method + WACC, sum less net debt.
- **DCF** (FCFF/FCFE): `engine/dcf_compute.py`. **DDM / P/B↔ROE** (banks): `engine/ddm_compute.py`. **NAV**: `engine/nav_compute.py`.
- **Per-segment / per-scenario value** (the analysts): `engine/scenario_value.py` — multiple primary + registry-method cross-check, computed not asserted, flags a >12% divergence.

## Not valuation methods (common confusion)
- **DuPont** decomposes ROE (a driver lens); it never outputs a price.
- **Gordon growth** is the perpetuity *inside* a DCF/DDM and the engine of the exit multiple; a building block, not a third engine.

## Deviation protocol
If the registry method does not fit, Daedalus may deviate but records why in `method_why`. Forseti flags
any unjustified deviation, any `business_type`/method mismatch, and any report missing the street
reconstruction, the numerator bridge, the sensitivity, or the surfaced crux.
