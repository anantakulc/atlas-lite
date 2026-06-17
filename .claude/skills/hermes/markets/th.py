"""Hermes TH adapter (STUB).

Intended source: Settrade Open API (requires API credentials). Thailand has the thinnest
open-source coverage of the set, so this is the last market to build.

Emit the same shape as BUNDLE_SCHEMA.md via normalize.write_bundle(). Model on us.py.
"""
import sys


def fetch(ticker, **kwargs):
    raise NotImplementedError(
        "Hermes TH adapter not built yet. Source: Settrade Open API (needs keys). "
        "Follow us.py and emit BUNDLE_SCHEMA.md."
    )


if __name__ == "__main__":
    sys.exit(fetch.__doc__)
