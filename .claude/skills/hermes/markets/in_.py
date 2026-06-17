"""Hermes IN adapter (STUB).

Intended sources: screener.in fundamentals (no official API — fetch + parse) plus yfinance for
prices/multiples on the .NS (NSE) or .BO (BSE) suffix. Indian banks are common, so map
`business_type_hint` to "bank" carefully.

Emit the same shape as BUNDLE_SCHEMA.md via normalize.write_bundle(). Model on us.py.
"""
import sys


def fetch(ticker, **kwargs):
    raise NotImplementedError(
        "Hermes IN adapter not built yet. Sources: screener.in + yfinance (.NS/.BO). "
        "Follow us.py and emit BUNDLE_SCHEMA.md."
    )


if __name__ == "__main__":
    sys.exit(fetch.__doc__)
