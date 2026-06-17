"""Hermes VN adapter (STUB).

Intended source: vnstock (the best-in-class Vietnam data library — stocks, financials, ratios).
This is the strongest EM data story of the set, so VN is the natural second market after US.

Emit the same shape as BUNDLE_SCHEMA.md via normalize.write_bundle(). Model on us.py.
"""
import sys


def fetch(ticker, **kwargs):
    raise NotImplementedError(
        "Hermes VN adapter not built yet. Source: vnstock (pip install vnstock). "
        "Follow us.py and emit BUNDLE_SCHEMA.md."
    )


if __name__ == "__main__":
    sys.exit(fetch.__doc__)
