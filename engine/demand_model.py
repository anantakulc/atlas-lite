"""demand_model.py — the deterministic demand/revenue trajectory engine (Theia, v2.3).

Theia (the LLM) authors SOURCED drivers; THIS script computes the year-by-year revenue path,
the gradual fade, and the reduced-form reconciliation. No invented curves: the trajectory is an
IDENTITY in the drivers, mirroring how the strongest AI-demand forecasts are actually built
(component demand = customer_capex x silicon-content-share x supplier-share, checked against a
historically-bounded conversion ratio).

Revenue formulas (pick per business):
  capex_content_share : revenue_t = customer_capex_t x layer_spend_share x supplier_share_t   (value-chain / AI supplier)
  endmarket_share     : revenue_t = end_market_t x share_t
  tam_penetration_share : revenue_t = tam_t x penetration_t x share_t                          (new-category adoption)
  units_asp           : revenue_t = units_t x asp_t

The FADE is EARNED, never a cliff: the LLM names the saturating quantity and the curve; Python
glides the primary driver's growth from its last sourced rate to terminal_g (logistic or linear),
so deceleration has a shape and a reason. The reduced-form check compares revenue/primary-driver
to the sourced historical ratio band and flags a break (a trending ratio = the identity is
changing = the contested lever the panel debates).

Usage:
    python demand_model.py --inputs output/<T>/<T>_demand_inputs.json --output output/<T>/<T>_demand.json

See theia.md for the input contract.
"""

import argparse
import json
import math
from pathlib import Path

ENGINE_VERSION = "theia-1.0"


def logistic_growth_glide(last_g, terminal_g, n, inflection=3, steepness=0.9):
    """Year-by-year growth rates gliding from last_g to terminal_g on an S-curve (a gradual,
    reasoned deceleration, not a step). inflection = the year the decel is steepest."""
    out = []
    for t in range(1, n + 1):
        w = 1.0 / (1.0 + math.exp(steepness * (t - inflection)))  # 1 -> 0 across the horizon
        out.append(round(terminal_g + (last_g - terminal_g) * w, 4))
    return out


def linear_growth_glide(last_g, terminal_g, n):
    return [round(last_g + (terminal_g - last_g) * (t / n), 4) for t in range(1, n + 1)]


def build_driver_path(driver, fade, horizon, start_year):
    """A driver path: explicit sourced values for the near years, then an EARNED fade for the rest.
    `driver` = {"sourced":[{year,value}], "label":..}; `fade` = {curve, terminal_g, inflection, steepness}."""
    sourced = sorted(driver.get("sourced", []), key=lambda x: x["year"])
    if not sourced:
        raise ValueError(f"driver '{driver.get('label')}' has no sourced values")
    path = [{"year": s["year"], "value": float(s["value"]), "source": "sourced"} for s in sourced]
    last = path[-1]["value"]
    # growth of the last sourced step (fall back to a stated last_growth)
    if len(path) >= 2 and path[-2]["value"]:
        last_g = path[-1]["value"] / path[-2]["value"] - 1.0
    else:
        last_g = fade.get("last_growth", 0.10)
    n_out = (start_year + horizon - 1) - path[-1]["year"]
    if n_out > 0:
        curve = fade.get("curve", "logistic")
        term = fade.get("terminal_g", 0.03)
        if curve == "linear":
            gpath = linear_growth_glide(last_g, term, n_out)
        else:  # logistic / capex_maturation / share_convergence all glide on an S-curve here
            gpath = logistic_growth_glide(last_g, term, n_out,
                                          fade.get("inflection", 3), fade.get("steepness", 0.9))
        v = last
        for i, g in enumerate(gpath):
            v = v * (1 + g)
            path.append({"year": path[-1]["year"] + 1 if False else sourced[-1]["year"] + i + 1,
                         "value": round(v, 4), "growth": g, "source": "faded"})
    return path, last_g


def share_at(path_spec, year, default):
    """A share/ratio that can be constant or pathed: {value} or {sourced:[{year,value}]}."""
    if path_spec is None:
        return default
    if "sourced" in path_spec:
        pts = sorted(path_spec["sourced"], key=lambda x: x["year"])
        prev = pts[0]["value"]
        for p in pts:
            if p["year"] <= year:
                prev = p["value"]
            else:
                break
        return float(prev)
    return float(path_spec.get("value", default))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    d = json.load(open(args.inputs, encoding="utf-8"))
    ticker = d["ticker"]
    formula = d["revenue_formula"]
    horizon = d.get("horizon_years", 10)
    start_year = d.get("start_year", 2026)
    drivers = d["drivers"]
    fade = d.get("fade", {})

    # ---- primary driver path (sourced near-term + earned fade) ----
    primary_key = {"capex_content_share": "customer_capex", "endmarket_share": "end_market",
                   "tam_penetration_share": "tam", "units_asp": "units"}[formula]
    primary = drivers[primary_key]
    dpath, last_g = build_driver_path(primary, fade, horizon, start_year)

    # ---- revenue identity ----
    rev_path = []
    for node in dpath:
        yr, drv = node["year"], node["value"]
        if formula == "capex_content_share":
            ls = share_at(drivers.get("layer_spend_share"), yr, 0.0)
            ss = share_at(drivers.get("supplier_share"), yr, 0.0)
            rev = drv * ls * ss
            terms = {"customer_capex": round(drv, 3), "layer_spend_share": ls, "supplier_share": ss}
        elif formula == "endmarket_share":
            ss = share_at(drivers.get("share"), yr, 0.0)
            rev = drv * ss
            terms = {"end_market": round(drv, 3), "share": ss}
        elif formula == "tam_penetration_share":
            pen = share_at(drivers.get("penetration"), yr, 0.0)
            ss = share_at(drivers.get("share"), yr, 0.0)
            rev = drv * pen * ss
            terms = {"tam": round(drv, 3), "penetration": pen, "share": ss}
        elif formula == "units_asp":
            asp = share_at(drivers.get("asp"), yr, 0.0)
            rev = drv * asp
            terms = {"units": round(drv, 3), "asp": asp}
        else:
            raise ValueError(f"unknown revenue_formula {formula}")
        rev_path.append({"year": yr, "revenue_usd_b": round(rev, 3), "primary_driver": round(drv, 3),
                         "terms": terms, "source": node["source"]})

    for i in range(1, len(rev_path)):
        prev = rev_path[i - 1]["revenue_usd_b"]
        rev_path[i]["yoy_pct"] = round((rev_path[i]["revenue_usd_b"] / prev - 1) * 100, 1) if prev else None
    rev_path[0]["yoy_pct"] = None

    # ---- reduced-form reconciliation: revenue / primary_driver vs the sourced historical band ----
    rec = d.get("reconcile", {})
    band = rec.get("historical_ratio_band")  # [lo, hi]
    recon = {"ratio_def": rec.get("ratio_def", "revenue / primary_driver"), "historical_band": band, "by_year": []}
    breaks = False
    for node in rev_path:
        drv = node["primary_driver"]
        ratio = round(node["revenue_usd_b"] / drv, 4) if drv else None
        in_band = (band is None) or (ratio is not None and band[0] <= ratio <= band[1])
        if not in_band:
            breaks = True
        recon["by_year"].append({"year": node["year"], "ratio": ratio, "in_band": in_band})
    recon["flag"] = "breaks_band" if breaks else ("within_band" if band else "no_band_supplied")

    # ---- TAM funnel (optional sanity bound) ----
    mkt = d.get("market", {})
    funnel = None
    tam0 = mkt.get("tam_usd_b")
    if tam0:
        sam = tam0 * mkt.get("sam_pct", 1.0)
        som = sam * mkt.get("som_share_pct", 0.0)
        funnel = {"tam_usd_b": tam0, "sam_usd_b": round(sam, 2), "som_usd_b": round(som, 2),
                  "triangulation_note": mkt.get("triangulation_note", "")}

    # ---- driver-ceiling reconciliation (v2.5): the IMPLIED primary driver (the spend pool / TAM that this
    # revenue path requires) at the horizon must not exceed a SOURCED, aggressive-but-credible ceiling. This is
    # the TAM/capex sanity GATE: it stops a cone bound (esp. the persistence/bull bound) from implying a
    # physically-senseless market -- e.g. an AVGO AI path that requires ~$3.8T of ANNUAL hyperscaler AI capex by
    # 2035 (~8x today). For capex_content_share the primary driver IS the customer-capex pool; for
    # tam_penetration_share it is the TAM; for endmarket_share the end market. Reconcile that driver, plus the
    # IMPLIED-TAM the revenue/share identity requires, against the sourced ceiling. No ceiling supplied -> no gate
    # (back-compatible), but Theia SHOULD always supply one for an AI/capex-cycle name. ----
    ceiling = mkt.get("driver_ceiling")  # {"year", "value_usd_b", "label", "source", "tier", "basis"}
    ceil_recon = None
    breaches_ceiling = False
    if ceiling and rev_path:
        cy = ceiling.get("year", rev_path[-1]["year"])
        cval = ceiling.get("value_usd_b")
        node_at = min(rev_path, key=lambda n: abs(n["year"] - cy))   # the path node nearest the ceiling year
        drv_at = node_at.get("primary_driver")
        headroom = round((cval - drv_at) / cval * 100, 1) if (cval and drv_at is not None) else None
        breaches_ceiling = bool(cval is not None and drv_at is not None and drv_at > cval)
        lbl = ceiling.get("label", primary.get("label", primary_key))
        ceil_recon = {
            "driver_label": lbl,
            "ceiling_year": cy, "ceiling_value_usd_b": cval,
            "ceiling_source": ceiling.get("source", ""), "ceiling_tier": ceiling.get("tier", ""),
            "ceiling_basis": ceiling.get("basis", ""),
            "implied_driver_at_ceiling_year": round(drv_at, 1) if drv_at is not None else None,
            "headroom_pct": headroom, "breaches_ceiling": breaches_ceiling,
            "verdict": (
                f"BREACH: this path implies {lbl} of ~${drv_at:,.0f}b at {cy}, ABOVE the sourced ceiling "
                f"(${cval:,.0f}b). The bound is not credible -- pull the driver/fade/share until it fits, or "
                f"re-source a higher ceiling." if breaches_ceiling else
                f"OK: implied {lbl} of ~${(drv_at or 0):,.0f}b at {cy} sits within the sourced ceiling "
                f"(${(cval or 0):,.0f}b), {headroom}% headroom."),
        }

    # ---- growth handoff to the valuation ----
    r0, rN = rev_path[0]["revenue_usd_b"], rev_path[-1]["revenue_usd_b"]
    yrs = rev_path[-1]["year"] - rev_path[0]["year"]
    cagr = round(((rN / r0) ** (1 / yrs) - 1) * 100, 1) if (r0 and yrs) else None
    cagr3 = None
    if len(rev_path) >= 4 and rev_path[0]["revenue_usd_b"]:
        cagr3 = round(((rev_path[3]["revenue_usd_b"] / rev_path[0]["revenue_usd_b"]) ** (1 / 3) - 1) * 100, 1)

    flags = list(d.get("flags", []))
    if recon["flag"] == "breaks_band":
        flags.append("conversion_ratio_breaks_historical_band")
    if mkt.get("tam_source_tier") in ("research_firm",) and not mkt.get("tam_bottom_up"):
        flags.append("tam_single_source_research_firm")
    if breaches_ceiling:
        flags.append("primary_driver_exceeds_sourced_ceiling")
    if ceiling is None:
        flags.append("no_driver_ceiling_supplied")

    out = {
        "ticker": ticker, "engine_version": ENGINE_VERSION, "as_of": d.get("as_of"),
        "revenue_formula": formula, "segment": d.get("segment"),
        "tam_funnel": funnel,
        "driver_ceiling_reconciliation": ceil_recon,
        "revenue_path": rev_path,
        "fade": {"saturating_quantity": fade.get("saturating_quantity"), "curve": fade.get("curve", "logistic"),
                 "terminal_g": fade.get("terminal_g", 0.03), "inflection_year": start_year + fade.get("inflection", 3) - 1,
                 "named_reason": fade.get("named_reason", ""), "last_sourced_growth_pct": round(last_g * 100, 1)},
        "reconciliation": recon,
        "growth_handoff": {"decade_revenue_cagr_pct": cagr, "cagr_3yr_pct": cagr3,
                           "revenue_path_b": [r["revenue_usd_b"] for r in rev_path],
                           "note": "feeds Daedalus's scenario triples as the SOURCED growth input"},
        "key_uncertainty": d.get("key_uncertainty", fade.get("named_reason", "")),
        "provenance": {"drivers_sourced": True, "fade_computed_by_engine": True},
        "flags": flags,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"[demand_model] {ticker} ({formula}): revenue {rev_path[0]['revenue_usd_b']} -> "
          f"{rev_path[-1]['revenue_usd_b']} ($b), decade CAGR {cagr}%, 3y {cagr3}%")
    print(f"  fade: {fade.get('curve','logistic')} on {fade.get('saturating_quantity','?')} "
          f"(last growth {round(last_g*100,1)}% -> terminal {round(fade.get('terminal_g',0.03)*100,1)}%)")
    print(f"  reconciliation: {recon['flag']}" + (f" (band {band})" if band else ""))
    if ceil_recon:
        print(f"  driver-ceiling: {'BREACH' if ceil_recon['breaches_ceiling'] else 'OK'} -- implied "
              f"{ceil_recon['driver_label']} {ceil_recon['implied_driver_at_ceiling_year']} vs ceiling "
              f"{ceil_recon['ceiling_value_usd_b']} @ {ceil_recon['ceiling_year']} ({ceil_recon['headroom_pct']}% headroom)")
    if flags:
        print(f"  flags: {flags}")


if __name__ == "__main__":
    main()
