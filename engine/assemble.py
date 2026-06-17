"""assemble.py — deterministic headline math for Atlas (v2: the four numbers).

The four numbers, the rating, and the conviction synthesis all live HERE, not in the LLM.
Reads output/<T>/<T>_valuation.json (intrinsic value + justified multiple), <T>_inputs.json
(WACC, dividend, the defensible 12m-target block), and <T>_comps.json (the street
reconstruction) and writes output/<T>/<T>_headline.json for Atlas to merge into <T>.json.

The four numbers (METHODS.md), each carrying its multiple:
  1. fair value today      — probability-weighted scenarios (intrinsic) + our justified multiple
  2. price today           — market + current multiple
  3. fair value in 12m     — #1 rolled forward at the fundamental rate, less dividend (pure convergence)
  4. target price in 12m   — defensible forward multiple x forward metric (where WE think it trades)

#3 and #4 are deliberately SEPARATE. #3 is what it's worth a year on; #4 is where it trades given the
multiple we will actually defend. The gap between them is the part of the call that rests on the market
continuing to pay — named explicitly, never bridged with a persistence fudge. The rating is off #4.

Usage:
    python assemble.py --ticker AVGO --bull-conviction HIGH --bear-conviction LOW \
                       --data-quality CLEAN --path-clarity MIXED --ensemble MEDIUM
"""
import argparse
import json
from pathlib import Path

BUY_HURDLE = 15.0     # implied 12m total return >= this -> BUY
SELL_HURDLE = -10.0   # <= this -> SELL
MOS_NORMAL = 12.0
MOS_LOW = 25.0

LEVEL = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
INV = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}
EV_BASES = {"EV/FCF", "EV/EBITDA", "EV/SALES", "EV/FCFF"}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def fair_value_from(val):
    """#1 fair value today = the BASE scenario's intrinsic value (v2.4 — NO probability weighting).
    The base (Metis) is the anchor; bull/bear are the range, never blended into #1."""
    scen = val.get("scenarios", [])
    for s in scen:
        if str(s.get("label", "")).lower() == "base" and s.get("implied_px") is not None:
            return round(s["implied_px"], 2)
    if val.get("fair_value_today") is not None:
        return round(val["fair_value_today"], 2)
    # last resort: a single explicitly flagged scenario, else the primary method output
    flagged = [s for s in scen if s.get("implied_px") is not None]
    if len(flagged) == 1:
        return round(flagged[0]["implied_px"], 2)
    return round(val["primary_method"]["outputs"]["implied_px"], 2)


def asymmetry_level(action, bull, bear):
    """Conviction LEVEL from the blind panel's self-conviction asymmetry (METHODS.md).
    A strong winning case against a weak opposing case is high conviction; two strong opposed
    cases are an earned MEDIUM; a weak winning case is LOW. Returns 0/1/2."""
    b, c = LEVEL.get(bull, 1), LEVEL.get(bear, 1)
    if action == "HOLD":
        return 1 if (b >= 2 and c >= 2) else 0   # genuine two-sided high debate -> MEDIUM, else LOW
    winner, loser = (b, c) if action == "BUY" else (c, b)
    if winner >= 2 and loser <= 0:
        return 2
    if winner >= 2:           # strong case but non-trivial opposition -> MEDIUM
        return 1
    if winner == 1:
        return 1 if loser < 2 else 0
    return 0                  # weak winning case -> LOW


def axis(level_bool_high, level_bool_low):
    return "HIGH" if level_bool_high else ("LOW" if level_bool_low else "MEDIUM")


def target_12m_from_inputs(t12, net_debt_b, shares_b):
    """#4 — the defensible traded price in 12m: our forward multiple x the 12m-forward metric.
    Returns (price, detail) or (None, None) if no defensible-multiple block was authored."""
    if not t12 or t12.get("defensible_multiple") is None or t12.get("forward_metric_value") is None:
        return None, None
    m = t12["defensible_multiple"]
    metric = t12["forward_metric_value"]
    basis = (t12.get("basis") or "EV/FCF").upper()
    value = m * metric
    if basis in EV_BASES:
        px = round((value - net_debt_b) / shares_b, 2) if shares_b else None
    else:  # P/E etc. — metric is per-share, multiple applies to price directly
        px = round(m * metric, 2)
    detail = {
        "basis": t12.get("basis"),
        "defensible_multiple": m,
        "forward_metric_label": t12.get("forward_metric_label", "forward metric"),
        "forward_metric_value": metric,
        "multiple_rationale": t12.get("multiple_rationale", ""),
        "price": px,
    }
    return px, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--bull-conviction", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"],
                    help="Boreas self_conviction in its own bull case")
    ap.add_argument("--bear-conviction", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"],
                    help="Cassandra self_conviction in its own bear case")
    ap.add_argument("--ensemble", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"],
                    help="stability from the 3x conclusion re-run (a split caps conviction)")
    ap.add_argument("--data-quality", default="CLEAN", choices=["CLEAN", "CORRECTED", "POOR"],
                    help="a corrected data artifact cannot be HIGH conviction")
    ap.add_argument("--path-clarity", default="MIXED", choices=["CLEAR", "MIXED", "UNCLEAR"],
                    help="catalyst/timing clarity -> the path-confidence axis")
    # Back-compat: --conviction maps to --ensemble if the new flags are left at default.
    ap.add_argument("--conviction", default=None, choices=["HIGH", "MEDIUM", "LOW"])
    # v2.4: Daedalus OWNS the conviction (his read of evidence quality across base/bull/bear).
    # When set, it is the base level; the data/band caps still apply as a sanity floor.
    ap.add_argument("--final-conviction", default=None, choices=["HIGH", "MEDIUM", "LOW"],
                    help="Daedalus's assigned conviction (v2.4 — overrides the panel-asymmetry calc)")
    args = ap.parse_args()
    t = args.ticker.upper()
    base = Path("output") / t
    if args.conviction and args.ensemble == "MEDIUM":
        args.ensemble = args.conviction

    val = load(base / f"{t}_valuation.json")
    inp = {}
    try:
        inp = load(base / f"{t}_inputs.json")
    except FileNotFoundError:
        pass
    comps = {}
    try:
        comps = load(base / f"{t}_comps.json")
    except FileNotFoundError:
        pass

    price = val.get("current_price")
    shares_b = val.get("shares_outstanding_b") or inp.get("shares_outstanding_b") or 0.0
    net_debt_b = val.get("net_debt_b", inp.get("net_debt_b", 0.0))
    fv = fair_value_from(val)

    wacc = 0.09
    try:
        wacc = inp["primary_method"]["inputs"]["wacc"]["value"]
    except (KeyError, TypeError):
        pass
    dps = inp.get("dividend_per_share") or 0.0

    # #3 fair value in 12m — pure intrinsic convergence (value carried forward at the fundamental rate)
    fv_12m = round(fv * (1 + wacc) - dps, 2)

    # #4 target price in 12m — defensible forward multiple x forward metric (where WE think it trades).
    # Falls back to #3 if no defensible-multiple block was authored (i.e. we assume convergence-to-intrinsic).
    target_12m, target_detail = target_12m_from_inputs(inp.get("target_12m"), net_debt_b, shares_b)
    target_basis = "defensible_multiple"
    if target_12m is None:
        target_12m = fv_12m
        target_basis = "intrinsic_convergence (no separate traded-multiple view authored)"

    pxs = [s["implied_px"] for s in val.get("scenarios", []) if s.get("implied_px") is not None]
    band_low = round(min(pxs), 2) if pxs else None
    band_high = round(max(pxs), 2) if pxs else None
    band_ratio = round((band_high - band_low) / fv, 3) if (band_low and band_high and fv) else None

    # Returns: to #4 (the rating), to #3 (pure convergence), and to the street (how much rests on the market)
    tr = round((target_12m + dps - price) / price * 100, 1) if price else None
    conv_return = round((fv_12m + dps - price) / price * 100, 1) if price else None
    street_mean = comps.get("street", {}).get("target_mean", {}).get("price")
    street_return = round((street_mean - price) / price * 100, 1) if (street_mean and price) else None

    if tr is None:
        action = "HOLD"
    elif tr >= BUY_HURDLE:
        action = "BUY"
    elif tr <= SELL_HURDLE:
        action = "SELL"
    else:
        action = "HOLD"
    tone = {"BUY": "positive", "SELL": "negative", "HOLD": "neutral"}[action]

    # Conviction (v2.4) — Daedalus's assigned read of evidence quality if provided, else the
    # legacy panel-asymmetry calc. Either way the data/band/stability caps apply as a sanity floor.
    if args.final_conviction:
        level = LEVEL[args.final_conviction]
        conviction_source = f"Daedalus assigned {args.final_conviction} (evidence read across base/bull/bear)"
    else:
        level = asymmetry_level(action, args.bull_conviction, args.bear_conviction)
        conviction_source = f"panel asymmetry: bull {args.bull_conviction} vs bear {args.bear_conviction}"
    caps = []
    if args.data_quality in ("CORRECTED", "POOR"):
        if level > 1:
            caps.append("data artifact corrected -> not HIGH")
        level = min(level, 1)
    if band_ratio is not None and band_ratio > 0.6:
        if level > 1:
            caps.append(f"wide scenario band ({band_ratio:.0%}) -> not HIGH")
        level = min(level, 1)
    if args.ensemble == "LOW":
        if level > 0:
            caps.append("ensemble split (instability) -> LOW")
        level = 0
    label = INV[level]

    valuation_confidence = axis(
        band_ratio is not None and band_ratio < 0.35 and args.data_quality == "CLEAN",
        band_ratio is not None and band_ratio > 0.6 or args.data_quality == "POOR",
    )
    # path confidence: from the timing/catalyst clarity, knocked down if the call leans on a re-rate
    # (target #4 materially above pure-intrinsic #3 means we are relying on the market keeping a premium)
    leans_on_market = (target_12m - fv_12m) / fv_12m > 0.10 if fv_12m else False
    path_base = {"CLEAR": 2, "MIXED": 1, "UNCLEAR": 0}[args.path_clarity]
    if leans_on_market and path_base > 0:
        path_base -= 1
    path_confidence = INV[path_base]

    mos = MOS_LOW if label == "LOW" else MOS_NORMAL

    # Multiples for the four-number block (the dual of each value)
    jm = val.get("justified_multiple", {}) or {}
    fv_multiple = jm.get("justified_ev_multiple") or jm.get("justified_pe_ntm")
    fv_multiple_label = ("EV/" + jm["ev_metric_label"]) if jm.get("ev_metric_label") else ("P/E " + str(jm.get("eps_ntm", "")) if jm.get("justified_pe_ntm") else None)
    price_multiple = jm.get("current_ev_multiple") or jm.get("current_pe_ntm")

    four_numbers = {
        "fair_value_today": {"value": fv, "multiple": fv_multiple, "multiple_label": fv_multiple_label,
                             "basis": "base case (Metis) intrinsic value — the anchor, not a weighted blend"},
        "price_today": {"value": price, "multiple": price_multiple, "multiple_label": fv_multiple_label,
                        "basis": "market"},
        "fair_value_12m": {"value": fv_12m, "basis": f"#1 rolled forward at r={wacc:.1%} less dividend {dps}",
                           "convergence_return_pct": conv_return},
        "target_12m": {"value": target_12m, "basis": target_basis, "detail": target_detail,
                       "implied_12m_total_return_pct": tr},
    }

    headline = {
        "valuation_headline": {  # kept flat for renderer / IntelliDesk compatibility
            "current_price": price,
            "fair_value_today": fv,
            "target_12m": target_12m,
            "fair_value_12m": fv_12m,
            "band_low": band_low,
            "band_high": band_high,
            "method_primary": val["primary_method"]["name"],
            "method_why": "",      # Daedalus fills this in <T>.json
        },
        "four_numbers": four_numbers,
        "street_reconstruction": comps.get("reconstruction") or {},
        "street_target": {
            "mean": street_mean,
            "mean_multiple": comps.get("street", {}).get("target_mean", {}).get("multiple"),
            "mean_implied_growth_pct": comps.get("street", {}).get("target_mean", {}).get("implied_growth_pct"),
            "high": comps.get("street", {}).get("target_high", {}).get("price"),
            "return_pct": street_return,
            "n_analysts": comps.get("street", {}).get("n_analysts"),
        },
        "rating": {
            "action": action,
            "tone": tone,
            "implied_12m_total_return_pct": tr,            # to #4 (the rating basis)
            "convergence_return_pct": conv_return,         # to #3 (pure intrinsic)
            "street_return_pct": street_return,            # to the street mean
            "hurdle_buy_pct": BUY_HURDLE,
            "hurdle_sell_pct": SELL_HURDLE,
            "margin_of_safety_pct": mos,
        },
        "conviction": {
            "label": label,
            "valuation_confidence": valuation_confidence,
            "path_confidence": path_confidence,
            "assigned_by": "daedalus" if args.final_conviction else "panel_asymmetry",
            "bull_self_conviction": args.bull_conviction,
            "bear_self_conviction": args.bear_conviction,
            "ensemble_stability": args.ensemble,
            "data_quality": args.data_quality,
            "band_ratio": band_ratio,
            "caps_applied": caps,
            "basis": (
                f"action {action}: {conviction_source} -> {label}"
                + ("; " + "; ".join(caps) if caps else "")
            ),
        },
        "sensitivity_matrix": val.get("sensitivity_matrix") or {},
        "bridge_logic": (
            f"#1 fair value today {fv} -> #3 fair value 12m {fv_12m} (x(1+{wacc:.3f}) - div {dps}); "
            f"#4 target 12m {target_12m} ({target_basis}); implied return to #4 = {tr}%, to #3 = {conv_return}%, "
            f"to street mean {street_mean} = {street_return}%"
        ),
    }

    out = base / f"{t}_headline.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(headline, f, indent=2, ensure_ascii=False)
    print(json.dumps(headline, indent=2))
    print(f"\n[assemble] wrote {out}")


if __name__ == "__main__":
    main()
