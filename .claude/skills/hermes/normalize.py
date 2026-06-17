"""Freeze a normalized data bundle to disk (see BUNDLE_SCHEMA.md).

Every Hermes market adapter calls write_bundle() so the Atlas engine always sees one shape,
regardless of which market or source produced it.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_id(ticker, dt):
    return f"{ticker.upper()}_{dt.strftime('%Y-%m-%dT%H%MZ')}"


def default_out(ticker):
    # cwd-relative, matching engine/render_*.py (the Atlas agent runs from the project root)
    return Path("output") / ticker.upper() / f"{ticker.upper()}_databundle.json"


def write_bundle(bundle, out_path=None):
    """Write the bundle JSON, creating output/<T>/ as needed. Returns the path."""
    ticker = bundle["_meta"]["ticker"]
    path = Path(out_path) if out_path else default_out(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    return path
