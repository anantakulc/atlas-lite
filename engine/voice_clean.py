"""voice_clean.py — mechanical prose cleanup on <T>.json (em dashes + AI tells).

Deterministic, regex-only. Walks every string value in the report JSON and cleans it, then
writes the file back. Run after Atlas assembles <T>.json and before rendering.

Usage:
    python voice_clean.py --ticker AVGO
"""
import argparse
import json
import re
from pathlib import Path

WORD_SUBS = [
    (r"\bdelve into\b", "dig into"),
    (r"\bDelve into\b", "Dig into"),
    (r"\btapestry\b", "mix"),
    (r"\bnevertheless\b", "still"),
    (r"\bNevertheless\b", "Still"),
    (r"\bmoreover\b", "also"),
    (r"\bfurthermore\b", "and"),
    (r"\bcould potentially\b", "could"),
    (r"\bit is worth noting that\b", ""),
    (r"\bIt is worth noting that\b", ""),
    (r"\bin the realm of\b", "in"),
    (r"\bunderscore[sd]?\b", "shows"),
]


def smart_em_dash(text):
    """Replace em/en dashes with context-aware punctuation (mirrors GER's voice_clean)."""
    # Numeric range: $123 — $456  ->  $123 to $456
    text = re.sub(r"(\$?\d[\d,\.]*)\s*[—–]\s*(\$?\d)", r"\1 to \2", text)

    def repl(m):
        after = m.group(1)
        if after and after[0].isupper():
            return ". " + after
        return "; "

    text = re.sub(r"\s*[—–]\s*([A-Za-z])", repl, text)
    return text.replace("—", ",").replace("–", ",")


def clean_text(s):
    s = smart_em_dash(s)
    for pat, rep in WORD_SUBS:
        s = re.sub(pat, rep, s)
    # collapse any double spaces the substitutions introduced
    s = re.sub(r"  +", " ", s).replace(" .", ".").replace(" ,", ",")
    return s.strip()


def walk(obj):
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        return [walk(x) for x in obj]
    if isinstance(obj, dict):
        return {k: walk(v) for k, v in obj.items()}
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    args = ap.parse_args()
    t = args.ticker.upper()
    path = Path("output") / t / f"{t}.json"
    data = json.load(open(path, encoding="utf-8"))
    cleaned = walk(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    print(f"[voice_clean] cleaned {path}")


if __name__ == "__main__":
    main()
