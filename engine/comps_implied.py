"""comps_implied.py — the market-implied / street-reconstruction layer (v2 step 2).

Runs BEFORE the DCF. A multiple is a compressed DCF; this script decompresses it.
Given where the stock trades and where the street's target sits, it solves what each
PRICE implies — in the industry's own currency (EV/FCF, EV/EBITDA, EV/Sales, P/E) —
and writes our justified-multiple grid. The output frames the debate (which lever is
contested) before Boreas/Cassandra argue and before Daedalus builds the full model.

This is the committed, deterministic home for the reverse-multiple math: same inputs in,
same reconstruction out, every run. The LLM authors the small comps inputs (the anchor
metric, the fundamental discount rate, the street figures); Python does the solving.

Usage:
    python comps_implied.py --inputs output/<T>/<T>_comps_inputs.json \
                            --output output/<T>/<T>_comps.json

See VALUATION_SCHEMA.md for the inputs/outputs shape.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

# Bases that capitalize an enterprise-level flow (solve on EV, bridge to price via net debt).
EV_BASES = {"EV/FCF", "EV/EBITDA", "EV/Sales", "EV/SALES", "EV/FCFF"}
# Bases that capitalize an equity-level flow per share (solve on price directly; r = cost of equity).
EQUITY_BASES = {"P/E", "P/FCF", "P/AFFO"}


def stream_value(metric0: float, conversion: float, g: float, r: float,
                 terminal_g: float, horizon: int) -> float:
    """Capitalized value of a cash stream the multiple implicitly discounts.

    flow_t = conversion * metric0 * (1+g)^t  for t = 1..horizon  (constant stage-1 growth),
    then a Gordon terminal at terminal_g. Returns the total present value (EV for EV bases,
    equity value for equity bases). conversion maps the anchor metric to free cash flow:
      EV/FCF      -> 1.0
      EV/EBITDA   -> FCF / EBITDA   (e.g. ~0.55-0.65)
      EV/Sales    -> steady-state FCF margin (so a pre-profit name's out-year FCF is modelled)
      P/E         -> payout / cash-conversion of earnings to FCFE
    A constant stage-1 growth then a terminal step is the standard "priced-in growth" lens;
    the precise valuation uses the faded path in dcf_compute.py. The two are different tools.
    """
    if r <= terminal_g:
        return float("inf")
    flow0 = conversion * metric0
    pv = 0.0
    f = flow0
    for t in range(1, horizon + 1):
        f = f * (1 + g)
        pv += f / (1 + r) ** t
    tv = f * (1 + terminal_g) / (r - terminal_g)
    pv += tv / (1 + r) ** horizon
    return pv


def solve_growth(target_value: float, metric0: float, conversion: float, r: float,
                 terminal_g: float, horizon: int) -> float:
    """Bisection: the constant stage-1 growth that makes stream_value == target_value."""
    if metric0 <= 0 or conversion == 0:
        return None
    lo, hi = -0.20, 0.60
    # Guard: if even the ceiling growth can't reach the target, the multiple is off-scale.
    if stream_value(metric0, conversion, hi, r, terminal_g, horizon) < target_value:
        return None
    if stream_value(metric0, conversion, lo, r, terminal_g, horizon) > target_value:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if stream_value(metric0, conversion, mid, r, terminal_g, horizon) < target_value:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def justified_single_stage_pe(g: float, roic: float, r: float) -> float:
    """The duality identity: justified forward P/E = (1 - g/ROIC) / (r - g).

    Decomposition tool, not the level for a high grower (it assumes perpetual g). Its value
    is showing the THREE levers: a re-rate from higher payout (higher ROIC at the same g)
    is visible here. Returns None when g >= r or g >= ROIC (single-stage undefined).
    """
    if roic is None or roic <= 0 or g >= r or g >= roic:
        return None
    payout = 1 - g / roic
    return round(payout / (r - g), 1)


def price_from_value(value: float, basis: str, net_debt_b: float, shares_b: float) -> float:
    """Bridge a capitalized value to price/share. EV bases subtract net debt; equity bases
    are already equity value ($b)."""
    if value is None or value == float("inf"):
        return None
    if basis.upper() in EV_BASES:
        return round((value - net_debt_b) / shares_b, 2) if shares_b else None
    return round(value / shares_b, 2) if shares_b else None


def value_from_price(price: float, basis: str, net_debt_b: float, shares_b: float) -> float:
    """Inverse: price/share -> capitalized value ($b). EV bases add net debt back."""
    equity_b = price * shares_b
    if basis.upper() in EV_BASES:
        return equity_b + net_debt_b
    return equity_b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    d = json.load(open(args.inputs, encoding="utf-8"))
    t = d["ticker"]
    price = d["current_price"]
    shares_b = d["shares_outstanding_b"]
    net_debt_b = d.get("net_debt_b", 0.0)
    r = d["fundamental_discount_rate"]
    terminal_g = d.get("terminal_growth", 0.03)
    horizon = d.get("horizon_years", 10)

    anchor = d["anchor"]
    basis = anchor["type"]
    metric0 = anchor["metric_value"]
    conv = anchor.get("fcf_conversion", 1.0)
    roic = anchor.get("roic")
    is_ev = basis.upper() in EV_BASES

    def reconstruct(px):
        """For a given price, return its capitalized value, the observed multiple, and the
        constant 10y growth it implies."""
        val = value_from_price(px, basis, net_debt_b, shares_b)
        mult = round(val / metric0, 1) if metric0 else None
        g_impl = solve_growth(val, metric0, conv, r, terminal_g, horizon)
        return {"price": round(px, 2), "value_b": round(val, 1), "multiple": mult,
                "implied_growth": g_impl,
                "implied_growth_pct": round(g_impl * 100, 1) if g_impl is not None else None}

    current = reconstruct(price)

    street = d.get("street", {}) or {}
    street_out = {"thesis": street.get("thesis", ""), "n_analysts": street.get("n_analysts"),
                  "rating": street.get("rating")}
    for k in ("target_mean", "target_high", "target_low"):
        if street.get(k) is not None:
            street_out[k] = reconstruct(street[k])

    # Our justified-multiple grid: for a range of growth, the multiple and price WE would pay.
    grid = []
    for g in d.get("justified_g_grid", [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25]):
        val = stream_value(metric0, conv, g, r, terminal_g, horizon)
        grid.append({
            "growth": g, "growth_pct": round(g * 100, 1),
            "justified_multiple": round(val / metric0, 1) if metric0 else None,
            "value_b": round(val, 1),
            "implied_price": price_from_value(val, basis, net_debt_b, shares_b),
        })

    # The duality decomposition (single-stage P/E identity): how ROIC/payout moves the multiple
    # at a fixed growth. Demonstrates that a re-rate can be a structural-ROIC claim, not just growth.
    duality = []
    roic_grid = d.get("roic_grid", [0.10, 0.20, 0.30, 0.50])
    for g in d.get("duality_g_grid", [0.04, 0.06, 0.08]):
        row = {"growth": g, "growth_pct": round(g * 100, 1)}
        for rc in roic_grid:
            row[f"roic_{int(rc*100)}"] = justified_single_stage_pe(g, rc, r)
        duality.append(row)

    peers = d.get("peers", [])
    peer_mults = [p["multiple"] for p in peers if p.get("multiple") is not None]
    peer_median = round(sorted(peer_mults)[len(peer_mults) // 2], 1) if peer_mults else None

    out = {
        "schema_version": "2.0",
        "ticker": t,
        "currency": d.get("currency", "USD"),
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "basis": basis,
        "metric_label": anchor.get("metric_label", basis),
        "metric_value": metric0,
        "fcf_conversion": conv,
        "roic": roic,
        "fundamental_discount_rate": r,
        "terminal_growth": terminal_g,
        "horizon_years": horizon,
        "current": current,
        "street": street_out,
        "history_context": d.get("history", {}),
        "justified_grid": grid,
        "duality_decomposition": {
            "note": "single-stage justified forward P/E = (1 - g/ROIC)/(r - g); shows the ROIC/payout lever",
            "r": r, "roic_columns": roic_grid, "rows": duality,
        },
        "peers": peers,
        "peer_median_multiple": peer_median,
        "reconstruction": {
            "currency": basis,
            "what_price_implies": (
                f"At {current['multiple']}x {anchor.get('metric_label', basis)}, the current price implies a "
                f"~{current['implied_growth_pct']}% {('FCF' if 'FCF' in basis or 'EBITDA' in basis else 'earnings')} "
                f"CAGR for {horizon}y (then {terminal_g*100:.0f}% terminal) at r={r*100:.1f}%."
            ) if current["implied_growth_pct"] is not None else
            f"At {current['multiple']}x, the price is above any finite growth this model spans at r={r*100:.1f}%.",
            "what_street_implies": (
                f"The street mean target implies ~{street_out['target_mean']['implied_growth_pct']}% for {horizon}y."
                if street_out.get("target_mean", {}).get("implied_growth_pct") is not None else ""
            ),
            "history_anchor": d.get("history", {}).get("note", ""),
            "contested_lever": d.get("contested_lever", ""),
        },
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"[OK] wrote {out_path}")
    print(f"  basis: {basis} on {anchor.get('metric_label', basis)} = {metric0}")
    print(f"  current: {current['multiple']}x -> implies {current['implied_growth_pct']}% {horizon}y growth")
    for k in ("target_mean", "target_high"):
        if k in street_out:
            s = street_out[k]
            print(f"  street {k}: ${s['price']} = {s['multiple']}x -> implies {s['implied_growth_pct']}%")
    if peer_median:
        print(f"  peer median multiple: {peer_median}x")


if __name__ == "__main__":
    main()
