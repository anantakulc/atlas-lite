"""score.py — deterministic gate checks for Forseti.

Forseti scores the FinRpt rubric with judgment; this does the MECHANICAL consistency checks that
need no judgment, and prints a checklist + an overall mechanical PASS/FAIL.

Usage:
    python score.py --ticker AVGO
"""
import argparse
import json
from pathlib import Path

METHODS_KEYS = {"bank", "insurer", "asset_manager", "reit", "miner_ep", "software",
                "industrial", "consumer", "telecom_utility", "highgrowth_preprofit",
                "cyclical", "conglomerate"}


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def approx(a, b, tol=0.5):
    return a is not None and b is not None and abs(a - b) <= tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    args = ap.parse_args()
    t = args.ticker.upper()
    base = Path("output") / t
    d = load(base / f"{t}.json")
    val = load(base / f"{t}_valuation.json")

    rt, vh, conv = d.get("rating", {}), d.get("valuation_headline", {}), d.get("conviction", {})
    tr, action = rt.get("implied_12m_total_return_pct"), rt.get("action")
    checks = []

    ok = True
    if action == "BUY" and (tr is None or tr < rt.get("hurdle_buy_pct", 15)):
        ok = False
    if action == "SELL" and (tr is None or tr > rt.get("hurdle_sell_pct", -10)):
        ok = False
    checks.append(("numbers_vs_narrative", ok, f"action={action}, implied 12m return={tr}"))

    pxs = [s.get("implied_px") for s in val.get("scenarios", []) if s.get("implied_px") is not None]
    band_ok = True
    if pxs:
        band_ok = approx(vh.get("band_low"), min(pxs)) and approx(vh.get("band_high"), max(pxs))
    checks.append(("band_matches_scenarios", band_ok, f"band=({vh.get('band_low')},{vh.get('band_high')})"))

    bt = d.get("business_type")
    checks.append(("business_type_valid", bt in METHODS_KEYS, f"business_type={bt}"))

    low_buy_ok = not (conv.get("label") == "LOW" and action == "BUY")
    checks.append(("low_conviction_buy_needs_mode", low_buy_ok,
                   "LOW-conviction BUY: confirm low-conviction mode + named pivot" if not low_buy_ok else "ok"))

    text = json.dumps(d, ensure_ascii=False)
    no_dash = ("—" not in text and "–" not in text)
    checks.append(("no_em_dashes", no_dash, "clean" if no_dash else "em/en dash survived voice_clean"))

    hard = ["numbers_vs_narrative", "band_matches_scenarios", "business_type_valid", "no_em_dashes"]
    overall = all(ok for name, ok, _ in checks if name in hard)

    print(f"Mechanical gate for {t}:")
    for name, ok, note in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {note}")
    print(f"\nMECHANICAL: {'PASS' if overall else 'FAIL'} (Forseti adds the rubric scores)")


if __name__ == "__main__":
    main()
