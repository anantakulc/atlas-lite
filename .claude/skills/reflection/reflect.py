"""reflect.py — the call ledger and mechanical calibration.

Records every Atlas call, resolves it against the realized outcome later, and recomputes the
calibration stats. Priors (HOUSE_VIEW.md) are NEVER touched here.

Usage:
    python reflect.py log      --ticker AVGO
    python reflect.py resolve  --ticker AVGO --realized-price 410 --breakers-fired 1 --blindsided false
    python reflect.py calibrate
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path("runs") / "ledger.jsonl"
CALIB = Path("charter") / "CALIBRATION.json"


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_ledger():
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_ledger(rows):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def do_log(t):
    d = load(Path("output") / t / f"{t}.json")
    rt, vh, conv = d.get("rating", {}), d.get("valuation_headline", {}), d.get("conviction", {})
    breakers = [k.get("what_flips") for k in d.get("key_debate", []) if k.get("what_flips")]
    entry = {
        "logged_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ticker": t,
        "date": d.get("date"),
        "snapshot_id": d.get("run_manifest", {}).get("snapshot_id"),
        "charter_version": d.get("run_manifest", {}).get("charter_version"),
        "action": rt.get("action"),
        "price_at_call": vh.get("current_price"),
        "target_12m": vh.get("target_12m"),
        "conviction": conv.get("label"),
        "pivot": conv.get("pivot"),
        "named_breakers": breakers,
        "status": "open",
    }
    rows = read_ledger()
    rows.append(entry)
    write_ledger(rows)
    print(f"[reflect] logged open call: {t} {entry['action']} target {entry['target_12m']} conviction {entry['conviction']}")


def do_resolve(t, realized_price, breakers_fired, blindsided):
    rows = read_ledger()
    target = None
    for r in reversed(rows):
        if r["ticker"] == t and r["status"] == "open":
            target = r
            break
    if not target:
        print(f"[reflect] no open call for {t}")
        return
    p0 = target.get("price_at_call")
    target["realized_price"] = realized_price
    target["realized_return_pct"] = round((realized_price - p0) / p0 * 100, 1) if p0 else None
    target["breakers_fired"] = breakers_fired
    target["blindsided"] = blindsided
    # decision quality: a loss where we named the risk that fired is GOOD process; blindsided is the lesson
    rr = target["realized_return_pct"]
    target["decision_quality"] = "blindsided" if blindsided else ("named-risk" if breakers_fired else "clean")
    target["direction_right"] = (target["action"] == "BUY" and rr is not None and rr > 0) or \
                                (target["action"] == "SELL" and rr is not None and rr < 0) or \
                                (target["action"] == "HOLD")
    target["status"] = "resolved"
    write_ledger(rows)
    print(f"[reflect] resolved {t}: realized {rr}%, direction_right={target['direction_right']}, quality={target['decision_quality']}")


def do_calibrate():
    rows = [r for r in read_ledger() if r.get("status") == "resolved"]
    calib = load(CALIB) or {"schema_version": "1.0"}
    conv_stats = {}
    for label in ("HIGH", "MEDIUM", "LOW"):
        sub = [r for r in rows if r.get("conviction") == label]
        n = len(sub)
        hits = sum(1 for r in sub if r.get("direction_right"))
        conv_stats[label] = {"n": n, "hit_rate": round(hits / n, 2) if n else None}
    blind = [r for r in rows if r.get("blindsided") is not None]
    named = [r for r in rows if r.get("breakers_fired") is not None]
    calib["conviction_reliability"] = conv_stats
    calib["named_risk_hit_rate"] = {"n": len(named),
                                    "rate": round(sum(1 for r in named if r.get("breakers_fired")) / len(named), 2) if named else None}
    calib["blindsided_rate"] = {"n": len(blind),
                                "rate": round(sum(1 for r in blind if r.get("blindsided")) / len(blind), 2) if blind else None}
    calib["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    calib["note"] = "Mechanical, auto-computed from resolved calls. Always shows N. Applied to FUTURE runs only. Does not edit HOUSE_VIEW.md."
    CALIB.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIB, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2, ensure_ascii=False)
    print(f"[reflect] calibrated on {len(rows)} resolved calls -> {CALIB}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log"); lg.add_argument("--ticker", required=True)
    rs = sub.add_parser("resolve")
    rs.add_argument("--ticker", required=True)
    rs.add_argument("--realized-price", type=float, required=True)
    rs.add_argument("--breakers-fired", type=int, default=0)
    rs.add_argument("--blindsided", default="false")
    sub.add_parser("calibrate")
    args = ap.parse_args()

    if args.cmd == "log":
        do_log(args.ticker.upper())
    elif args.cmd == "resolve":
        do_resolve(args.ticker.upper(), args.realized_price, args.breakers_fired,
                   str(args.blindsided).lower() in ("true", "1", "yes"))
    elif args.cmd == "calibrate":
        do_calibrate()


if __name__ == "__main__":
    main()
