---
name: scorecard
description: The FinRpt-style quality rubric and the deterministic gate checks Forseti uses to pass or bounce a report. Use when grading a finished <T>.json before it ships.
---

# Scorecard — the quality gate

Two layers, used together by Forseti:

## 1. The rubric (judgment — Forseti scores this)
Score the report's 6 sections 1-5 (the FinRpt ERR dimensions):
- Financial-numeric precision
- News / catalyst relevance
- Company / market / industry insight
- Investment-rationale quality
- Risk thoroughness (and is Cassandra's bear engaged, not strawmanned?)
- Writing (deductive, one idea per unit, plain register, no undefined jargon)

**Bar: every section >= 3, rationale and risk >= 4.** Below bar -> REVISE with the specific fix.

## 2. The mechanical checks (no judgment — `score.py` does this)
```
python .claude/skills/scorecard/score.py --ticker AVGO
```
Deterministic consistency checks that don't need an LLM:
- numbers vs narrative (a BUY must clear the buy hurdle; a SELL must be below the sell hurdle)
- scenario band matches the min/max scenario implied price
- `business_type` is a real METHODS.md key
- low-conviction BUY is flagged for the low-conviction-mode check
- no em dashes survived voice_clean

Forseti combines the rubric scores with `score.py`'s checklist into a single SHIP / REVISE verdict.
