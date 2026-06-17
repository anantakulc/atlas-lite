"""reverse_dcf.py — what is the market pricing in?

Inverts the DCF: holds the WACC, horizon, and terminal growth from <T>_inputs.json, fixes year-1
FCF, and solves for the FCF CAGR over the remaining years that makes the DCF fair value equal the
CURRENT PRICE. Answers "at $X, the market is pricing ~g% FCF growth" — the discipline against a
pure-fundamental SELL that misses what the market is assuming.

Usage:
    python reverse_dcf.py --ticker AVGO
"""
import argparse
import json
from pathlib import Path


def dcf_ev(fcf1, g, wacc, horizon, term_g):
    pv = fcf1 / (1 + wacc)
    fcf = fcf1
    for t in range(2, horizon + 1):
        fcf = fcf * (1 + g)
        pv += fcf / ((1 + wacc) ** t)
    tg = min(term_g, g, wacc - 0.005)
    tv = fcf * (1 + tg) / (wacc - tg)
    pv += tv / ((1 + wacc) ** horizon)
    return pv


def implied_growth(target_ev, fcf1, wacc, horizon, term_g):
    lo, hi = -0.5, 1.5
    for _ in range(80):
        mid = (lo + hi) / 2
        if dcf_ev(fcf1, mid, wacc, horizon, term_g) < target_ev:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    args = ap.parse_args()
    t = args.ticker.upper()
    inp = json.load(open(Path("output") / t / f"{t}_inputs.json", encoding="utf-8"))
    pm = inp["primary_method"]["inputs"]
    price = inp["current_price"]
    shares = inp["shares_outstanding_b"]
    net_debt = inp.get("net_debt_b", 0.0)
    wacc = pm["wacc"]["value"]
    term_g = max(pm["terminal_growth"]["value"], 0.04)
    proj = pm["fcf_projections"]
    horizon = len(proj)
    fcf1 = proj[0]["fcf_b"]

    target_ev = price * shares + net_debt
    g_implied = implied_growth(target_ev, fcf1, wacc, horizon, term_g)
    g_base = (proj[-1]["fcf_b"] / proj[0]["fcf_b"]) ** (1 / (horizon - 1)) - 1 if horizon > 1 and proj[0]["fcf_b"] else None

    out = {
        "current_price": price,
        "wacc": wacc,
        "horizon_years": horizon,
        "implied_fcf_cagr_pct": round(g_implied * 100, 1),
        "base_case_fcf_cagr_pct": round(g_base * 100, 1) if g_base is not None else None,
        "reading": f"At {price}, holding WACC {round(wacc*100,1)}%, the market is pricing ~{round(g_implied*100,1)}% FCF growth for {horizon} years"
                   + (f", vs our base case of ~{round(g_base*100,1)}%." if g_base is not None else "."),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
