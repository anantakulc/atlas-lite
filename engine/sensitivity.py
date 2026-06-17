"""sensitivity.py - Atlas v2.4 sensitivity matrix around the BASE case.

The user's v2.4 mandate: Daedalus does not blend the three cases into one number.
He anchors on the base and builds a SENSITIVITY MATRIX over the two levers the
call actually hinges on, then leans the 12m target off the base by a documented
judgment. This script builds that matrix deterministically.

For an AI-capex name the two levers are:
  - X axis: post-2027 AI-demand PERSISTENCE  (the semi owner-FCF path: reversion
    -> measured-base -> persistence, the bear/base/bull cone)
  - Y axis: r  (the discount rate / WACC: street ~8.75% -> base 9.15% -> bear 10.25%)

Each cell runs the SAME SOTP math the panel used (semi DCF + software multiple),
holding the SOFTWARE segment at the BASE multiple so the grid isolates the two
SEMICONDUCTOR levers. The three named cases (bear/base/bull) carry their own
software multiple too, so they are validated separately and annotated onto the grid.

It reads the three driver files (<T>_{base,bull,bear}_drivers.json) so it is
reusable across tickers with the same conglomerate driver shape.

Usage:
    python sensitivity.py --ticker AVGO --output output/AVGO/AVGO_sensitivity.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dcf_compute import compute_dcf_outputs


def load(p):
    return json.load(open(p, encoding="utf-8"))


def lerp_path(a, b, t):
    """Linear interpolation between two FCF paths, year by year."""
    return [round(x + (y - x) * t, 3) for x, y in zip(a, b)]


def segments_of(drivers):
    return drivers["crosscheck"]["segments"]


def semi_seg(drivers):
    return [s for s in segments_of(drivers) if "Semi" in s["name"]][0]


def software_seg(drivers):
    cand = [s for s in segments_of(drivers) if "Software" in s["name"] or "VMware" in s["name"]]
    return cand[0] if cand else None


def semi_ev(fcf_path, wacc, terminal_g, horizon=10):
    """EV of the semi segment given a FCF path, r, and terminal g (net debt handled at parent)."""
    seg_inputs = {
        "wacc": {"value": wacc},
        "terminal_growth": {"value": terminal_g},
        "forecast_horizon_years": horizon,
        "fcf_projections": [{"year": 2026 + i, "fcf_b": f} for i, f in enumerate(fcf_path)],
    }
    out = compute_dcf_outputs(seg_inputs, 0.0, 1.0, build_trace=False)
    return out["implied_ev_b"]


def software_ev(drivers):
    s = software_seg(drivers)
    if not s:
        return 0.0
    mi = s["multiple_inputs"]
    return round(mi["multiple_value"] * mi["fy_estimate"], 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    t = args.ticker.upper()
    base_dir = Path("output") / t

    base = load(base_dir / f"{t}_base_drivers.json")
    bull = load(base_dir / f"{t}_bull_drivers.json")
    bear = load(base_dir / f"{t}_bear_drivers.json")

    net_debt_b = base["net_debt_b"]
    shares_b = base["shares_outstanding_b"]
    price = base["current_price"]

    base_semi, bull_semi, bear_semi = semi_seg(base), semi_seg(bull), semi_seg(bear)
    base_path = [p["fcf_b"] for p in base_semi["dcf_inputs"]["fcf_projections"]]
    bull_path = [p["fcf_b"] for p in bull_semi["dcf_inputs"]["fcf_projections"]]
    bear_path = [p["fcf_b"] for p in bear_semi["dcf_inputs"]["fcf_projections"]]
    base_tg = base_semi["dcf_inputs"]["terminal_growth"]["value"]
    bull_tg = bull_semi["dcf_inputs"]["terminal_growth"]["value"]
    bear_tg = bear_semi["dcf_inputs"]["terminal_growth"]["value"]
    base_r = base_semi["dcf_inputs"]["wacc"]["value"]
    bull_r = bull_semi["dcf_inputs"]["wacc"]["value"]
    bear_r = bear_semi["dcf_inputs"]["wacc"]["value"]

    # Software held at BASE multiple across the grid (isolate the two semi levers)
    soft_ev_base = software_ev(base)

    # ---- the two axes -------------------------------------------------------
    # X (demand persistence): 5 columns from reversion to persistence
    demand_cols = [
        {"label": "reversion (bear)", "path": bear_path, "tg": bear_tg},
        {"label": "reversion->base", "path": lerp_path(bear_path, base_path, 0.5), "tg": round((bear_tg + base_tg) / 2, 4)},
        {"label": "measured (base)", "path": base_path, "tg": base_tg},
        {"label": "base->persistence", "path": lerp_path(base_path, bull_path, 0.5), "tg": base_tg},
        {"label": "persistence (bull)", "path": bull_path, "tg": bull_tg},
    ]
    # Y (discount rate): 5 rows from street to bear
    r_rows = [bull_r, round((bull_r + base_r) / 2, 5), base_r, round((base_r + bear_r) / 2, 5), bear_r]

    # ---- the grid -----------------------------------------------------------
    def cell_px(path, wacc, tg):
        ev = semi_ev(path, wacc, tg) + soft_ev_base
        return round((ev - net_debt_b) / shares_b, 2)

    grid = []
    for r in r_rows:
        row = [cell_px(c["path"], r, c["tg"]) for c in demand_cols]
        grid.append(row)

    # ---- named-case validation (own software multiple + own r) --------------
    def named_px(drivers):
        s = semi_seg(drivers)["dcf_inputs"]
        ev = semi_ev([p["fcf_b"] for p in s["fcf_projections"]], s["wacc"]["value"], s["terminal_growth"]["value"]) + software_ev(drivers)
        return round((ev - net_debt_b) / shares_b, 2)

    named = {
        "bear": {"recomputed_px": named_px(bear), "r": bear_r, "col": "reversion (bear)",
                 "panel_sotp_px": bear["crosscheck"].get("segments") and None},
        "base": {"recomputed_px": named_px(base), "r": base_r, "col": "measured (base)"},
        "bull": {"recomputed_px": named_px(bull), "r": bull_r, "col": "persistence (bull)"},
    }

    out = {
        "ticker": t,
        "method": "Atlas v2.4 sensitivity matrix (SOTP; software held at base multiple to isolate the two semi levers)",
        "current_price": price,
        "anchor": "base case (Metis) intrinsic value",
        "axis_x": {"lever": "post-2027 AI-demand persistence (semi owner-FCF path)",
                   "columns": [c["label"] for c in demand_cols],
                   "note": "reversion=Theia reversion bound, measured=Metis base, persistence=Theia persistence bound; the two interior columns are year-by-year interpolations"},
        "axis_y": {"lever": "discount rate r (WACC)",
                   "rows_pct": [round(r * 100, 2) for r in r_rows],
                   "note": "8.75%=street-implied, 9.15%=Metis fundamental WACC, 10.25%=bear (concentration+cyclicality charged explicitly)"},
        "grid": grid,
        "grid_rows_r_pct": [round(r * 100, 2) for r in r_rows],
        "grid_cols_demand": [c["label"] for c in demand_cols],
        "software_held_at": {"segment": "Infrastructure Software (VMware)", "ev_b": soft_ev_base,
                             "note": "held at base 15x across the grid; the named bull/bear also flex software +/-1 turn (a ~$3-7/sh effect) shown in the case table, not in the grid"},
        "named_cases": named,
        "base_cell": {"r_pct": round(base_r * 100, 2), "col": "measured (base)",
                      "value": cell_px(base_path, base_r, base_tg)},
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # readable print
    print(f"[sensitivity] {t} — SOTP value ($/sh) over demand persistence (cols) x r (rows)")
    hdr = "  r\\demand |" + "".join(f"{c['label'][:16]:>17}" for c in demand_cols)
    print(hdr)
    for r, row in zip(r_rows, grid):
        print(f"  {r*100:6.2f}%  |" + "".join(f"{v:>17.0f}" for v in row))
    print(f"\n  named-case recompute (own software mult + own r): "
          f"bear {named['bear']['recomputed_px']}, base {named['base']['recomputed_px']}, bull {named['bull']['recomputed_px']}")
    print(f"  price {price}; base anchor cell {out['base_cell']['value']}")
    print(f"[sensitivity] wrote {args.output}")


if __name__ == "__main__":
    main()
