"""scenario_value.py — the per-scenario valuation tool the analysts run (v2.2).

Each analyst (Metis = base, Boreas = bull, Cassandra = bear) authors ONE scenario's explicit
drivers and runs this to get a COMPUTED value — never an asserted one. It values the scenario
TWO ways and shows where they agree:

  1. MULTIPLE (primary, comparable to the street): justified_multiple x forward_metric -> per share.
     This is how the street prices the name, so it is how we see where WE differ. General across
     currencies (EV/EBITDA, EV/Sales, P/E, P/B).
  2. INTRINSIC cross-check — BY THE REGISTRY METHOD for the business_type (METHODS.md), NOT always a DCF:
     DCF (most), SOTP (conglomerate), DDM (bank), NAV (REIT/miner). The cross-check's implied multiple is
     shown beside the street's so the two lenses reconcile.

NO reverse-DCF. Growth, the numerator (capex/tax/working-capital/SBC-net-of-buyback all inside the cash
flow), and r are explicit drivers. The tool reuses the SAME engine math Daedalus and Erinys use.

Usage:
    python scenario_value.py --inputs output/<T>/<T>_<label>_drivers.json --output output/<T>/<T>_<label>_value.json

Inputs (the `crosscheck.method` MUST match the METHODS.md registry for the business_type):
{
  "label":"base", "ticker":"AVGO", "current_price":393.94, "net_debt_b":48.958, "shares_outstanding_b":4.758,
  "multiple_valuation": {"multiple_type":"EV/EBITDA","justified_multiple":22.0,
                         "forward_metric_label":"FY2026E adj-EBITDA","forward_metric_value":74.0,"rationale":"..."},
  "crosscheck": {
     "method":"DCF",  // or "SOTP" | "DDM" | "NAV"
     // DCF: base_fcf0_b, (growth_path | stage1_growth+fade_start_year+terminal_g), r, terminal_g, horizon, numerator_note
     // SOTP: segments:[ {name, method:"DCF"|"Multiple", dcf_inputs{...}|multiple_inputs{...}, net_debt_allocation_b} ]
  }
}
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dcf_compute import (
    compute_dcf_outputs,
    compute_multiple_outputs,
    linear_fade_path,
    fcf_path_from_growth,
)
from sotp_compute import value_segment, aggregate_segments

EV_TYPES = {"EV/EBITDA", "EV/SALES", "EV/FCF", "EV/FCFF"}


def run_crosscheck(cc, nd, sh, start_year_default=2026):
    """Return (px, ev, method, detail) for the registry-method intrinsic cross-check."""
    method = cc.get("method", "DCF").upper()

    if method == "DCF":
        horizon = cc.get("horizon", 10)
        start_year = cc.get("start_year", start_year_default)
        path = cc["growth_path"] if "growth_path" in cc else linear_fade_path(
            cc["stage1_growth"], cc["terminal_g"], horizon, cc.get("fade_start_year", 3))
        proj = fcf_path_from_growth(cc["base_fcf0_b"], path, start_year)
        out = compute_dcf_outputs(
            {"wacc": {"value": cc["r"]}, "terminal_growth": {"value": cc["terminal_g"]},
             "forecast_horizon_years": horizon, "fcf_projections": proj}, nd, sh)
        return out["implied_px"], out.get("implied_ev_b"), "DCF", {"growth_path": path, "base_fcf0_b": cc["base_fcf0_b"]}

    if method == "SOTP":
        segs = cc["segments"]
        seg_out = [value_segment(s, nd, sh) for s in segs]
        agg = aggregate_segments(seg_out, nd, sh)
        return agg["implied_px"], agg["sum_of_segment_ev_b"], "SOTP", {
            "segments": [{"name": s["name"], "ev_b": s["outputs"].get("implied_ev_b")} for s in seg_out]}

    if method in ("DDM", "NAV"):
        # Banks (DDM, P/B<->ROE) and REIT/miner (NAV) route to their own engines, same pattern.
        raise NotImplementedError(
            f"crosscheck method {method}: run engine/{method.lower()}_compute.py for the intrinsic cross-check "
            f"(this tool currently wires DCF + SOTP; add the {method} branch when that market goes live).")

    raise ValueError(f"Unknown crosscheck method: {method}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    d = json.load(open(args.inputs, encoding="utf-8"))
    label = d.get("label", "scenario")
    price = d["current_price"]
    nd = d.get("net_debt_b", 0.0)
    sh = d["shares_outstanding_b"]

    # ---- 1. MULTIPLE valuation (primary, street-comparable) ----
    mv = d["multiple_valuation"]
    mult_out = compute_multiple_outputs(
        {"multiple_type": mv["multiple_type"], "peer_median_multiple": mv["justified_multiple"],
         "fy_estimate": mv["forward_metric_value"]}, nd, sh)
    mult_px = mult_out["implied_px"]

    # ---- 2. INTRINSIC cross-check by the REGISTRY METHOD ----
    cc_px, cc_ev, cc_method, cc_detail = run_crosscheck(d["crosscheck"], nd, sh)

    fm_val = mv["forward_metric_value"]
    is_ev = mv["multiple_type"].upper() in EV_TYPES
    if is_ev and cc_ev and fm_val:
        cc_implied_mult = round(cc_ev / fm_val, 1)
    elif (not is_ev) and cc_px and fm_val:
        cc_implied_mult = round(cc_px / fm_val, 1)
    else:
        cc_implied_mult = None

    gap_pct = round((cc_px - mult_px) / mult_px * 100, 1) if (mult_px and cc_px) else None

    out = {
        "label": label, "ticker": d.get("ticker"), "current_price": price,
        # MULTIPLE (primary)
        "multiple_type": mv["multiple_type"], "justified_multiple": mv["justified_multiple"],
        "forward_metric_label": mv.get("forward_metric_label"), "forward_metric_value": fm_val,
        "multiple_value_per_share": mult_px, "multiple_implied_ev_b": mult_out.get("implied_ev_b"),
        "multiple_rationale": mv.get("rationale", ""),
        # INTRINSIC cross-check (registry method)
        "crosscheck_method": cc_method,
        "crosscheck_value_per_share": cc_px, "crosscheck_implied_ev_b": cc_ev,
        "crosscheck_implied_multiple_same_metric": cc_implied_mult, "crosscheck_detail": cc_detail,
        "numerator_note": d["crosscheck"].get("numerator_note", ""),
        # reconciliation
        "method_gap_pct": gap_pct, "method_agree": (gap_pct is not None and abs(gap_pct) <= 12),
        # headline: MULTIPLE is primary (street-comparable); the registry cross-check validates it
        "value_per_share": mult_px,
        "vs_price_pct": round((mult_px - price) / price * 100, 1) if (mult_px and price) else None,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"[scenario_value] {label}: MULTIPLE {mv['justified_multiple']}x {mv['multiple_type']} on "
          f"{fm_val} -> ${mult_px}/sh ({out['vs_price_pct']:+}% vs price)")
    print(f"  {cc_method} cross-check: ${cc_px}/sh (implied {cc_implied_mult}x same metric); "
          f"methods {'AGREE' if out['method_agree'] else 'DIVERGE'} ({gap_pct:+}%)")
    if not out["method_agree"]:
        print(f"  ! multiple and {cc_method} diverge >12% -- reconcile the justified multiple with the cash-flow drivers.")


if __name__ == "__main__":
    main()
