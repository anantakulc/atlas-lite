"""edgar_capex.py — sourced customer/hyperscaler capex from SEC EDGAR XBRL (Theia data connector, v2.3).

The spine of every value-chain demand model: pull the buyers' ACTUAL annual capex straight from
EDGAR's structured XBRL, so the demand identity (component_demand = customer_capex x content x share)
rests on filed data, not a guessed market number. No API key; SEC requires a descriptive User-Agent
and rate-limits to ~10 req/s.

Capex is tagged inconsistently across filers, so we use a FALLBACK CHAIN and record which tag hit:
  1. PaymentsToAcquirePropertyPlantAndEquipment   (most common, the pure PP&E line)
  2. PaymentsToAcquireProductiveAssets            (parent; PP&E + software/intangibles — some filers tag here)
Forward capex GUIDANCE (e.g. "$190B incl. finance leases") is NOT in XBRL — Theia/Pheme extract that from
transcripts as a sourced quote; this connector returns the audited HISTORY the demand fade is anchored to.

Usage:
    python edgar_capex.py --tickers MSFT,GOOGL,AMZN,META --output output/_shared/hyperscaler_capex.json
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

UA = "Atlas Research atlas-research@example.com"  # SEC requires a descriptive UA; replace with a real contact
CONCEPTS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
_CACHE = Path(__file__).resolve().parents[2] / "runs" / ".edgar_cache"


def _get(url, ttl=86400):
    _CACHE.mkdir(parents=True, exist_ok=True)
    key = _CACHE / (url.split("//", 1)[-1].replace("/", "_") + ".json")
    if key.exists() and (time.time() - key.stat().st_mtime) < ttl:
        return json.load(open(key, encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
        obj = json.loads(data)
    json.dump(obj, open(key, "w", encoding="utf-8"))
    time.sleep(0.15)  # be polite, stay well under 10 req/s
    return obj


def ticker_to_cik(ticker):
    m = _get("https://www.sec.gov/files/company_tickers.json")
    for row in m.values():
        if row["ticker"].upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    raise ValueError(f"CIK not found for {ticker}")


def _annual_from_concept(cik, concept):
    """Annual full-year (10-K) values for one concept: {fy: value_usd_b}, dedup by fiscal year keeping the
    LATEST-FILED value (handles restatements). Relies on duration + form, NOT fp (filers tag fp inconsistently)."""
    try:
        obj = _get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json")
    except Exception:
        return {}
    by_fy = {}  # fy -> (val_b, filed)
    for f in obj.get("units", {}).get("USD", []):
        start, end, form, filed = f.get("start"), f.get("end"), f.get("form", ""), f.get("filed", "")
        if not start or not end or form != "10-K":
            continue
        days = (int(end[:4]) - int(start[:4])) * 365 + (int(end[5:7]) - int(start[5:7])) * 30
        if not (330 <= days <= 400):
            continue
        fy = int(end[:4])  # the DATA POINT's fiscal year = its period-end year (NOT the filing's fy field,
                            # which is the same across the 3-year comparatives inside one 10-K)
        if fy not in by_fy or filed > by_fy[fy][1]:
            by_fy[fy] = (round(f["val"] / 1e9, 3), filed)
    return {fy: v for fy, (v, _) in by_fy.items()}


def annual_capex(ticker):
    """Return {ticker, cik, tag_used, annual_capex_usd_b, source}. Tries every tag in the fallback chain and
    PICKS THE ONE THAT COVERS THE MOST RECENT YEARS (filers switch tags — e.g. AMZN moved PP&E ->
    ProductiveAssets), instead of stopping at the first non-empty tag."""
    cik = ticker_to_cik(ticker)
    candidates = {c: _annual_from_concept(cik, c) for c in CONCEPTS}
    candidates = {c: s for c, s in candidates.items() if s}
    if not candidates:
        return {"ticker": ticker.upper(), "cik": cik, "tag_used": None, "annual_capex_usd_b": {},
                "source": "SEC EDGAR XBRL", "note": "no capex tag in the fallback chain returned annual data"}
    # best = the tag whose series reaches the latest fiscal year (tiebreak: most years)
    best = max(candidates, key=lambda c: (max(candidates[c]), len(candidates[c])))
    note = None
    if len(candidates) > 1:
        note = "multiple capex tags present; used the one covering the most recent years: " + \
               ", ".join(f"{c}->{max(s)}" for c, s in candidates.items())
    out = {"ticker": ticker.upper(), "cik": cik, "tag_used": best,
           "annual_capex_usd_b": dict(sorted(candidates[best].items())),
           "source": f"SEC EDGAR XBRL us-gaap:{best} (10-K full-year)"}
    if note:
        out["tag_note"] = note
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", required=True, help="comma-separated, e.g. MSFT,GOOGL,AMZN,META")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    per = {}
    for t in tickers:
        try:
            per[t.upper()] = annual_capex(t)
        except Exception as e:
            per[t.upper()] = {"ticker": t.upper(), "error": str(e), "annual_capex_usd_b": {}}

    # aggregate (the end-market capex driver) — sum across buyers per fiscal year, only years all report
    years = [set(v.get("annual_capex_usd_b", {}).keys()) for v in per.values() if v.get("annual_capex_usd_b")]
    common = sorted(set.intersection(*years)) if years else []
    agg = {y: round(sum(per[t]["annual_capex_usd_b"][y] for t in per
                        if str(y) in map(str, per[t].get("annual_capex_usd_b", {}))
                        or y in per[t].get("annual_capex_usd_b", {})), 2) for y in common}

    out = {"buyers": tickers, "per_buyer": per, "aggregate_capex_usd_b": agg,
           "note": "Audited 10-K capex history (XBRL). Forward guidance lives in transcripts (Theia/Pheme extract, with the 'capex + finance leases' caveat).",
           "ua_used": UA}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    for t, v in per.items():
        a = v.get("annual_capex_usd_b", {})
        last = sorted(a.items())[-3:] if a else []
        print(f"  {t}: tag={v.get('tag_used')}  recent capex($b)={last}")
    print(f"  aggregate (common years): {agg}")
    print(f"[edgar_capex] wrote {args.output}")


if __name__ == "__main__":
    main()
