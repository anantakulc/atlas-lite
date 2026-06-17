"""nav_compute.py — Net Asset Value engine for resources (miners / E&P) and REITs.

The methods GER lacked. Same CLI and output contract as dcf_compute.py so render/assemble are
method-agnostic. NAV = PV of period net cash flows (production x margin, or NOI) + PV terminal
+ other assets - net debt, divided by shares -> implied equity value per share. Scenarios apply
multipliers to the cash flows and discount rate.

Inputs (output/<T>/<T>_inputs.json), primary_method.name == "NAV":
  inputs: {
    discount_rate: 0.10,
    cashflows: [ {year: 2026, net_cash_b: 4.2}, ... ],   # net of operating cost
    terminal_value_b: 12.0,            # optional, undiscounted at last year
    other_assets_b: 1.0,               # optional
  }
scenarios: [{label, probability, key_changes:{discount_rate?, cashflow_multiplier?}}]

Usage:
    python nav_compute.py --inputs AVGO_inputs.json --output AVGO_valuation.json
"""
import argparse
import json
from datetime import datetime, timezone


def nav(cashflows, disc, terminal_b=0.0, other_b=0.0, net_debt_b=0.0, cf_mult=1.0):
    pv = 0.0
    last_year = None
    base_year = cashflows[0]["year"] if cashflows else 0
    for i, cf in enumerate(cashflows, start=1):
        pv += (cf["net_cash_b"] * cf_mult) / ((1 + disc) ** i)
        last_year = i
    if terminal_b and last_year:
        pv += (terminal_b * cf_mult) / ((1 + disc) ** last_year)
    equity_b = pv + other_b - net_debt_b
    return pv, equity_b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    inp = json.load(open(args.inputs, encoding="utf-8"))
    pm = inp["primary_method"]["inputs"]
    shares = inp["shares_outstanding_b"]
    net_debt = inp.get("net_debt_b", 0.0)
    disc = pm["discount_rate"]
    cfs = pm["cashflows"]
    terminal = pm.get("terminal_value_b", 0.0)
    other = pm.get("other_assets_b", 0.0)

    pv, equity_b = nav(cfs, disc, terminal, other, net_debt)
    implied_px = round(equity_b / shares, 2)

    scenarios = []
    for s in inp.get("scenarios", []):
        kc = s.get("key_changes", {})
        d = kc.get("discount_rate", disc)
        mult = kc.get("cashflow_multiplier", 1.0)
        _, eq = nav(cfs, d, terminal, other, net_debt, cf_mult=mult)
        scenarios.append({
            "label": s["label"],
            "implied_px": round(eq / shares, 2),
            "probability": s.get("probability"),
        })

    fv = implied_px
    pxs = [x["implied_px"] for x in scenarios if x["implied_px"] is not None]
    if scenarios and all(x["probability"] is not None for x in scenarios):
        fv = round(sum(x["implied_px"] * x["probability"] for x in scenarios), 2)

    out = {
        "schema_version": "1.0",
        "ticker": inp["ticker"],
        "currency": inp.get("currency", "USD"),
        "current_price": inp.get("current_price"),
        "shares_outstanding_b": shares,
        "net_debt_b": net_debt,
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "primary_method": {
            "name": "NAV",
            "category": "intrinsic",
            "reasoning": inp["primary_method"].get("reasoning", ""),
            "outputs": {
                "pv_cashflows_b": round(pv, 3),
                "implied_equity_b": round(equity_b, 3),
                "implied_px": implied_px,
            },
        },
        "cross_check": inp.get("cross_check", {}),
        "scenarios": scenarios,
        "fair_value_today": fv,
        "blended_target": None,    # assemble.py computes the 12m roll-forward target
        "upside_pct": round((fv - inp["current_price"]) / inp["current_price"] * 100, 1)
        if inp.get("current_price") else None,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"[nav_compute] wrote {args.output} (implied_px {implied_px})")


if __name__ == "__main__":
    main()
