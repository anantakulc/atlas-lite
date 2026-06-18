"""
engine/bundle_slice.py — per-agent views of the frozen databundle.

Each agent only needs a slice of the full bundle. Passing the full ~80k-token
bundle to every agent wastes ~20% of each run's tokens. This module creates
named views sized to each agent's actual needs:

  theia    — competitive landscape work: profile, segments, peers, revenue context only
  pheme    — market intelligence: price (full), multiples, estimates, analyst data, filings
  daedalus — full valuation model: all financials, FCF components, multiples, segments, peers
  debate   — Boreas/Cassandra crux quantification: lightweight key financials + estimates

Usage:
    python engine/bundle_slice.py --bundle output/NFLX/NFLX_databundle.json --for theia
    # writes output/NFLX/NFLX_bundle_theia.json and prints the path to stdout

Library:
    from engine.bundle_slice import slice_bundle
    theia_data = slice_bundle(bundle_dict, "theia")
"""

import argparse
import json
from pathlib import Path


def _pick(obj: dict, keys: list) -> dict:
    return {k: obj[k] for k in keys if k in obj}


def _filter_rows(rows: list, fields: list) -> list:
    return [_pick(row, fields) for row in rows]


def slice_bundle(bundle: dict, agent: str) -> dict:
    """Return a sliced copy of bundle for the named agent."""
    if agent == "theia":
        return _slice_theia(bundle)
    if agent == "pheme":
        return _slice_pheme(bundle)
    if agent == "daedalus":
        return _slice_daedalus(bundle)
    if agent == "debate":
        return _slice_debate(bundle)
    raise ValueError(f"Unknown agent slice '{agent}'. Valid: theia, pheme, daedalus, debate")


def _slice_theia(b: dict) -> dict:
    """
    Theia maps the business, segments, competition, addressable market.
    Doesn't need full financial model or FCF components — just growth/margin context.
    Approximate saving vs full bundle: 50-65%.
    """
    out: dict = {}
    for k in ("_meta", "profile", "segments", "peers"):
        if k in b:
            out[k] = b[k]

    if "price" in b:
        out["price"] = _pick(b["price"], [
            "current", "asof", "high_52w", "low_52w", "ytd_pct", "return_1y_pct", "beta",
        ])

    if "market_stats" in b:
        out["market_stats"] = _pick(b["market_stats"], [
            "market_cap_b", "shares_outstanding_b", "adtv_usd_m",
        ])

    if "estimates" in b:
        out["estimates"] = _pick(b["estimates"], [
            "revenue_ntm_b", "eps_ntm", "num_analysts", "rec_mean",
        ])

    if "financials" in b:
        fin = b["financials"]
        income_fields = ["fy", "revenue_b", "gross_profit_b", "ebit_b", "ebitda_b"]
        out["financials"] = {}
        if "income" in fin:
            out["financials"]["income"] = _filter_rows(fin["income"], income_fields)

    return out


def _slice_pheme(b: dict) -> dict:
    """
    Pheme freezes market facts: what's priced in, analyst tape, sentiment.
    Needs full price, multiples, estimates, peers, filings — not FCF detail.
    Approximate saving vs full bundle: 30-40%.
    """
    out: dict = {}
    for k in ("_meta", "profile", "price", "market_stats", "valuation_multiples",
              "estimates", "peers", "filings", "segments"):
        if k in b:
            out[k] = b[k]

    if "financials" in b:
        fin = b["financials"]
        income_fields = ["fy", "revenue_b", "ebit_b", "net_income_b", "eps"]
        cashflow_fields = ["fy", "cfo_b", "fcf_b", "buybacks_b", "dividends_paid_b"]
        out["financials"] = {}
        if "income" in fin:
            out["financials"]["income"] = _filter_rows(fin["income"], income_fields)
        if "cashflow" in fin:
            out["financials"]["cashflow"] = _filter_rows(fin["cashflow"], cashflow_fields)

    return out


def _slice_daedalus(b: dict) -> dict:
    """
    Daedalus builds the full valuation model. Gets the complete bundle.
    This slice is effectively a pass-through — Daedalus needs everything.
    Included here for API uniformity; provides no token saving.
    """
    return dict(b)


def _slice_debate(b: dict) -> dict:
    """
    Boreas and Cassandra debate the crux. They read crux.json and valuation.json
    primarily; this slice gives them just enough bundle context for quantification.
    Approximate saving vs full bundle: 70-80%.
    """
    out: dict = {}
    for k in ("_meta", "profile"):
        if k in b:
            out[k] = b[k]

    if "price" in b:
        out["price"] = _pick(b["price"], ["current", "asof"])

    if "market_stats" in b:
        out["market_stats"] = _pick(b["market_stats"], [
            "market_cap_b", "shares_outstanding_b", "net_debt_b",
        ])

    if "estimates" in b:
        out["estimates"] = _pick(b["estimates"], [
            "revenue_ntm_b", "eps_ntm", "target_mean", "target_median", "num_analysts",
        ])

    if "financials" in b:
        fin = b["financials"]
        income_fields = ["fy", "revenue_b", "ebit_b", "net_income_b", "eps"]
        cashflow_fields = ["fy", "fcf_b"]
        out["financials"] = {}
        if "income" in fin:
            out["financials"]["income"] = _filter_rows(fin["income"], income_fields)
        if "cashflow" in fin:
            out["financials"]["cashflow"] = _filter_rows(fin["cashflow"], cashflow_fields)

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Slice a frozen databundle to the per-agent view."
    )
    parser.add_argument("--bundle", required=True, help="Path to <T>_databundle.json")
    parser.add_argument("--for", dest="agent", required=True,
                        choices=["theia", "pheme", "daedalus", "debate"],
                        help="Target agent name")
    parser.add_argument("--output", help="Output path (default: auto-named beside bundle)")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)

    sliced = slice_bundle(bundle, args.agent)

    if args.output:
        out_path = Path(args.output)
    else:
        ticker = bundle.get("_meta", {}).get("ticker") or bundle_path.stem.split("_")[0]
        out_path = bundle_path.parent / f"{ticker}_bundle_{args.agent}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sliced, f, indent=2, ensure_ascii=False)

    print(str(out_path))


if __name__ == "__main__":
    main()
