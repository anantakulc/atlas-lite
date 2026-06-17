# runs/ — the call ledger

`ledger.jsonl` is the append-only record of every Atlas call (one JSON object per line). It is
the data the learning loop calibrates on. It's created on the first `reflect.py log`.

Each line, when first logged, is an **open** call:
```json
{"logged_utc":"...","ticker":"AVGO","date":"2026-06-15","snapshot_id":"AVGO_...","charter_version":"1.0.0",
 "action":"BUY","price_at_call":382.07,"target_12m":420.0,"conviction":"HIGH","pivot":"VMware margin",
 "named_breakers":["two quarters of VMware deferred-revenue decline"],"status":"open"}
```

Later, `reflect.py resolve` closes it with the realized outcome and a **decision-quality** tag:
- `clean` — call worked, no named breaker fired.
- `named-risk` — a risk we explicitly named fired (good process, even if the call lost).
- `blindsided` — hit by a risk we never listed (the real lesson; this is what should drive a
  human-approved charter amendment).

`reflect.py calibrate` rolls resolved calls into `charter/CALIBRATION.json` (mechanical, shows N,
applied to future runs only). It never edits `HOUSE_VIEW.md`.
