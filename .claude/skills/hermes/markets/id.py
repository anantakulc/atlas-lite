"""Hermes ID adapter (STUB).

Intended sources: IDX disclosure portal + yfinance on the .JK suffix, with the option to read
cached filings from _shared/data_lake (Indonesia already has lake coverage and a price keeper).
Indonesian banks use the DDM path, so set business_type_hint to "bank" for the BUKU IV names.

Emit the same shape as BUNDLE_SCHEMA.md via normalize.write_bundle(). Model on us.py.
"""
import sys


def fetch(ticker, **kwargs):
    raise NotImplementedError(
        "Hermes ID adapter not built yet. Sources: IDX + yfinance (.JK) + _shared/data_lake. "
        "Follow us.py and emit BUNDLE_SCHEMA.md."
    )


if __name__ == "__main__":
    sys.exit(fetch.__doc__)
