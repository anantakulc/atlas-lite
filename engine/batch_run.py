"""
engine/batch_run.py — parallel data freeze for multi-stock batch runs.

For a 3-stock batch in one Pro session window, the single biggest non-analysis
saving is running all three Hermes data fetches in parallel before any agent
starts. Each Hermes call is mostly network I/O (yfinance + EDGAR); running them
serially wastes wall-clock time and burns Pro session messages on waiting.

This script dispatches all Hermes fetches in parallel threads, waits for all to
complete, and prints a ready-list the Atlas agent uses to pipeline the per-stock
analysis sequentially (each stock at ~150-200k tokens on Sonnet).

Usage:
    python engine/batch_run.py --tickers NFLX AAPL MSFT
    python engine/batch_run.py --tickers NFLX AAPL MSFT --force-refresh

After this completes, dispatch the Atlas agent for each ready ticker in sequence.
Each per-stock analysis is independent and does not compete for context.
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run_hermes(ticker: str, force: bool = False, root: Path = Path(".")) -> tuple[str, bool, str]:
    """Run Hermes for one ticker. Returns (ticker, success, stdout/stderr snippet)."""
    script = root / ".claude" / "skills" / "hermes" / "us.py"
    cmd = [sys.executable, str(script), "--ticker", ticker]
    if force:
        cmd.append("--force-refresh")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, cwd=str(root),
        )
        if result.returncode == 0:
            snippet = (result.stdout or "").strip().splitlines()[-1] if result.stdout else "done"
            return ticker, True, snippet
        msg = (result.stderr or result.stdout or "unknown error").strip()
        return ticker, False, msg[:200]
    except subprocess.TimeoutExpired:
        return ticker, False, "timed out after 180s"
    except Exception as exc:
        return ticker, False, str(exc)


def freeze_all(
    tickers: list[str], force: bool = False, root: Path = Path(".")
) -> dict[str, bool]:
    """Freeze all tickers in parallel. Returns {ticker: success}."""
    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=len(tickers)) as pool:
        futures = {pool.submit(run_hermes, t, force, root): t for t in tickers}
        for future in as_completed(futures):
            ticker, ok, msg = future.result()
            results[ticker] = ok
            status = "OK  " if ok else "FAIL"
            print(f"  [{status}] {ticker}: {msg}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Parallel Hermes data freeze for a batch of tickers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python engine/batch_run.py --tickers NFLX AAPL MSFT
  python engine/batch_run.py --tickers NVDA META GOOGL --force-refresh

After the freeze completes, process each ready ticker through Atlas sequentially.
Per-stock token budget on Sonnet with optimizations: ~150-200k tokens each.
Three stocks: ~500-600k total — fits comfortably in one Pro session window.
""",
    )
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Re-fetch even if a bundle already exists",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    print(f"Freezing {len(args.tickers)} ticker(s) in parallel: {', '.join(args.tickers)}\n")
    results = freeze_all(args.tickers, force=args.force_refresh, root=root)

    ready = [t for t, ok in results.items() if ok]
    failed = [t for t, ok in results.items() if not ok]

    print(f"\nReady for analysis ({len(ready)}): {', '.join(ready) or 'none'}")
    if failed:
        print(f"Failed ({len(failed)}):           {', '.join(failed)}")

    if ready:
        print("\nDispatch Atlas for each ticker in sequence (do NOT parallelize analysis):")
        for i, t in enumerate(ready, 1):
            bundle = root / "output" / t / f"{t}_databundle.json"
            print(f"  {i}. {t}  [bundle: {bundle}]")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
