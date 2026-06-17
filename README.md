# Atlas

A multi-market, thesis-driven equity research engine. One ticker in → a coherent research report
out (PDF + Excel + JSON), graded by a quality gate, with conviction measured rather than asserted.

Built to behave like the **same analyst every run**: a pinned house view, frozen data snapshots,
deterministic valuation math, and a prior-run diff, so results are consistent and replicable.

- **Agents** (`.claude/agents/`): Atlas, Boreas, Cassandra, Daedalus, Erinys, Forseti.
- **Data** (`.claude/skills/hermes/`): per-market adapters that freeze a data bundle. US is live (yfinance + SEC).
- **Engine** (`engine/`): DCF / DDM / SOTP / NAV compute + the report renderers.
- **Charter** (`charter/`): the pinned analyst — house view, method registry, style, calibration.
- **Deploy** (`deploy/`): JSON-only publish to the IntelliDesk web app.

See `CLAUDE.md` for the full operating manual.
