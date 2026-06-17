---
name: reflection
description: The call ledger and mechanical calibration. Logs every Atlas call, resolves it later against the realized outcome, and recomputes the calibration stats. Priors are never auto-tuned here.
---

# Reflection — the learning loop (recording side)

Atlas records every call from day one so the analyst can be calibrated later. The learning is
split: **calibration is mechanical and bounded; priors change only with human sign-off.** You
can't overfit zero data, so the calibrate step does nothing useful until calls resolve.

```
python .claude/skills/reflection/reflect.py log      --ticker AVGO
python .claude/skills/reflection/reflect.py resolve  --ticker AVGO --realized-price 410 --breakers-fired 1 --blindsided false
python .claude/skills/reflection/reflect.py calibrate
```

- **log** appends an open call to `runs/ledger.jsonl` (date, snapshot, charter version, action, price, 12m target, conviction, the pivot, the named breakers).
- **resolve** closes a call against the realized price and records which *named* breakers fired and whether we were blindsided by an unlisted one (the real lesson; grade decision quality, not luck).
- **calibrate** recomputes `charter/CALIBRATION.json` from resolved calls only: conviction hit-rate, target error, named-risk hit-rate, blindsided-rate. Always shows N. Applied to FUTURE runs only.

What this never does: edit `HOUSE_VIEW.md`. Process priors change through a human-approved,
versioned amendment, proposed only from patterns across many resolved calls.
