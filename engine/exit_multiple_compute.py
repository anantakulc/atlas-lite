"""exit_multiple_compute.py — the clean high-growth valuation method (Atlas v3, CONTRACT.md §2.2).

Value a high-growth segment by: build owner-earnings (NOPAT) to a NORMALIZATION YEAR T (when growth has
matured to a steady single-digit rate), apply a WELL-BEHAVED steady-state multiple (a single-stage Gordon
P/E — valid there because in steady state g < r), and discount back at the segment's WACC. This avoids the
two failures of a forced 10-year perpetual DCF on a fast grower: the g > r blow-up, and smuggling the ramp
into ROIC. It is also robust to the choice of T (the answer barely moves whether you normalize at T or T±2).

    exit EV/NOPAT  =  (1 - g_lt / ROIC) / (r - g_lt)     # the steady-state multiple — an OUTPUT, not a pick
    EV_today       =  NOPAT_T * exit_multiple / (1+r)^T   ( + PV of interim FCF years 1..T, optional )

NOPAT is unlevered after-tax operating profit, so the Gordon on it yields ENTERPRISE value (net debt is
netted once, at the SOTP group level). Quote the exit multiple and reconcile it to where mature comparables
trade (CONTRACT §3 lever 4).

Usage (standalone, one segment):
    python exit_multiple_compute.py --inputs <name>_exit_inputs.json --output <name>_exit.json

Importable: compute_exit_multiple_outputs(inputs, net_debt_b, shares_b) -> dict with implied_ev_b.

Inputs JSON:
{
  "nopat_T_b": 96.3,            // NOPAT at the normalization year  (OR nopat_path_b + normalize_index)
  "nopat_path_b": [...],        // optional: the NOPAT path; with normalize_index picks NOPAT_T
  "normalize_index": 5,         // index into nopat_path_b for year T
  "years_to_T": 5,              // T, years from the valuation date (end of base year) to normalization
  "g_lt": 0.045,               // long-run sustainable growth (must be < r)
  "roic": 0.45,                // steady-state incremental ROIC
  "r": 0.094,                  // the SEGMENT WACC
  "exit_multiple_override": null,   // optional: pin the EV/NOPAT multiple instead of computing the Gordon
  "interim_fcf_pv_b": 0.0,     // optional: PV today of FCF thrown off years 1..T (a pure exit-multiple omits it)
  "reasoning": "..."
}
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def gordon_multiple(g_lt: float, roic: float, r: float) -> float:
    """Steady-state EV/NOPAT (= justified forward multiple): (1 - g/ROIC)/(r - g). Requires r > g."""
    if r <= g_lt:
        raise ValueError(f"exit multiple needs r ({r}) > g_lt ({g_lt}); in steady state growth must be below the discount rate")
    payout = 1.0 - (g_lt / roic if roic else 0.0)
    return payout / (r - g_lt)


def compute_exit_multiple_outputs(inputs: dict, net_debt_b: float, shares_b: float) -> dict:
    r = inputs["r"]
    g_lt = inputs["g_lt"]
    roic = inputs.get("roic", 0.0)
    T = inputs["years_to_T"]

    # NOPAT at the normalization year
    if "nopat_T_b" in inputs and inputs["nopat_T_b"] is not None:
        nopat_T = inputs["nopat_T_b"]
    else:
        nopat_T = inputs["nopat_path_b"][inputs["normalize_index"]]

    exit_mult = inputs.get("exit_multiple_override")
    exit_mult_computed = round(gordon_multiple(g_lt, roic, r), 2)
    if exit_mult is None:
        exit_mult = exit_mult_computed

    value_T = nopat_T * exit_mult                  # EV at year T
    disc = (1 + r) ** T
    ev_today = value_T / disc + inputs.get("interim_fcf_pv_b", 0.0)
    implied_equity = ev_today - net_debt_b
    implied_px = implied_equity / shares_b if shares_b else None

    return {
        "method": "ExitMultiple",
        "nopat_T_b": round(nopat_T, 3),
        "years_to_T": T,
        "g_lt": g_lt,
        "roic": roic,
        "r": r,
        "exit_multiple": exit_mult,
        "exit_multiple_gordon": exit_mult_computed,   # the formula value, for the reader to check the override
        "ev_at_T_b": round(value_T, 3),
        "discount_factor": round(disc, 4),
        "interim_fcf_pv_b": inputs.get("interim_fcf_pv_b", 0.0),
        "implied_ev_b": round(ev_today, 3),
        "implied_equity_b": round(implied_equity, 3),
        "implied_px": round(implied_px, 2) if implied_px is not None else None,
    }


def t_invariance_check(inputs: dict, net_debt_b: float, shares_b: float) -> list:
    """Re-value at T-2 .. T+2 (using the NOPAT path) so the analyst can verify the answer is ~T-invariant.
    A large spread means the exit multiple and the growth path disagree (CONTRACT §2.2 step 3)."""
    if "nopat_path_b" not in inputs or "normalize_index" not in inputs:
        return []
    path = inputs["nopat_path_b"]
    idx0 = inputs["normalize_index"]
    T0 = inputs["years_to_T"]
    out = []
    for d in (-2, -1, 0, 1, 2):
        idx = idx0 + d
        if 0 <= idx < len(path):
            ti = dict(inputs)
            ti["nopat_T_b"] = path[idx]
            ti["years_to_T"] = T0 + d
            o = compute_exit_multiple_outputs(ti, net_debt_b, shares_b)
            out.append({"T": T0 + d, "nopat_T_b": round(path[idx], 1), "implied_px": o["implied_px"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    d = json.load(open(args.inputs, encoding="utf-8"))
    nd = d.get("net_debt_b", 0.0)
    sh = d["shares_outstanding_b"]
    out = compute_exit_multiple_outputs(d, nd, sh)
    out["t_invariance"] = t_invariance_check(d, nd, sh)
    out["ticker"] = d.get("ticker")
    out["computed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[exit_multiple] NOPAT_T {out['nopat_T_b']} x {out['exit_multiple']}x (Gordon {out['exit_multiple_gordon']}x) "
          f"/ (1+{out['r']})^{out['years_to_T']} = EV ${out['implied_ev_b']}b -> ${out['implied_px']}/sh")
    if out["t_invariance"]:
        print("  T-invariance:", ", ".join(f"T{c['T']}=${c['implied_px']}" for c in out["t_invariance"]))


if __name__ == "__main__":
    main()
