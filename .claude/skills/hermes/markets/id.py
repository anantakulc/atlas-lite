"""Hermes ID adapter — fetch and freeze a data bundle for an IDX-listed Indonesian ticker.

Sources:
  - yfinance : price, market stats, multiples, annual financials (uses .JK suffix for IDX tickers)
  - IDX EFTS : recent filing pointers (best-effort; silently skipped if unreachable)
  - Google News: recent headlines (best-effort)

Writes output/<T>/<T>_databundle.json (BUNDLE_SCHEMA.md). Money fields are in IDR billions (_b).
Defensive by design: any field a source doesn't provide is omitted and logged to _meta.gaps.

Notes:
  - Indonesian multifinance/banks (BUKU IV) → business_type_hint "bank" for the DDM path.
  - Ticker input: "BFIN" → yfinance queries "BFIN.JK". Already-suffixed tickers pass through.
  - IDR figures: 1 IDR billion ≈ USD 60K at 16,500 IDR/USD. Market cap in IDR T = _b / 1000.

Usage:
    python markets/id.py --ticker BFIN
    python markets/id.py --ticker BFIN --out output/BFIN/BFIN_databundle.json
    python markets/id.py --ticker BFIN --no-idx   # skip the IDX filing call (offline)
"""
import argparse
import json
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import normalize as nz

try:
    import yfinance as yf
except ImportError:
    sys.exit("ERROR: yfinance not installed. Run: pip install yfinance")

IDX_UA = "Atlas Research algothinks@gmail.com"


# ---------- safe coercions ----------
def num(x):
    try:
        f = float(x)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def to_b(x):
    """Convert raw IDR value to IDR billions."""
    f = num(x)
    return round(f / 1e9, 3) if f is not None else None


def pct(x):
    f = num(x)
    return round(f * 100, 2) if f is not None else None


# ---------- yfinance helpers ----------
def _jk(ticker):
    """Ensure .JK suffix for IDX tickers."""
    t = ticker.upper()
    return t if t.endswith(".JK") else t + ".JK"


def _stmt(tk, *attrs):
    for a in attrs:
        try:
            df = getattr(tk, a)
        except Exception:
            df = None
        if df is not None and getattr(df, "empty", True) is False:
            return df
    return None


def _cell(df, col, *labels):
    for lab in labels:
        if lab in df.index:
            v = num(df.loc[lab, col])
            if v is not None:
                return v
    return None


def _fy(col):
    try:
        return "FY" + str(col.year)
    except Exception:
        return str(col)


def _fget(fi, *keys):
    for k in keys:
        v = None
        try:
            v = fi[k]
        except Exception:
            try:
                v = getattr(fi, k)
            except Exception:
                v = None
        if v is not None:
            return num(v)
    return None


def biz_hint(sector, industry):
    s, i = (sector or "").lower(), (industry or "").lower()
    if any(k in i for k in ["bank", "banking"]):
        return "bank"
    if any(k in i for k in ["credit service", "consumer finance", "multifinance", "finance"]):
        return "bank"          # DDM path — multifinance pays high dividends, regulated like banks
    if "insurance" in i:
        return "insurer"
    if "asset management" in i or "capital markets" in i:
        return "asset_manager"
    if "reit" in i or "real estate" in s:
        return "reit"
    if any(k in i for k in ["coal", "mining", "metal", "nickel", "gold", "palm oil", "plantation"]):
        return "miner_ep"
    if any(k in i for k in ["telecom", "utilit", "tower"]):
        return "telecom_utility"
    if "software" in i or "technology" in s:
        return "software"
    if any(k in s for k in ["consumer", "retail"]):
        return "consumer"
    return "industrial"


# ---------- financials ----------
def build_income(tk):
    df = _stmt(tk, "income_stmt", "financials")
    if df is None:
        return [], ["income statement unavailable"]
    rows = []
    for col in list(df.columns)[:6]:
        rows.append({
            "fy": _fy(col),
            "revenue_b": to_b(_cell(df, col, "Total Revenue", "Operating Revenue")),
            "gross_profit_b": to_b(_cell(df, col, "Gross Profit")),
            "ebit_b": to_b(_cell(df, col, "Operating Income", "EBIT")),
            "ebitda_b": to_b(_cell(df, col, "EBITDA", "Normalized EBITDA")),
            "net_income_b": to_b(_cell(df, col, "Net Income", "Net Income Common Stockholders",
                                        "Net Income From Continuing Operation Net Minority Interest")),
            "eps": num(_cell(df, col, "Diluted EPS", "Basic EPS")),
            "shares_b": to_b(_cell(df, col, "Diluted Average Shares", "Basic Average Shares")),
            "interest_expense_b": to_b(_cell(df, col, "Interest Expense",
                                              "Interest Expense Non Operating")),
        })
    return rows, []


def build_balance(tk):
    df = _stmt(tk, "balance_sheet", "balancesheet")
    if df is None:
        return [], ["balance sheet unavailable"]
    rows = []
    for col in list(df.columns)[:6]:
        rows.append({
            "fy": _fy(col),
            "cash_b": to_b(_cell(df, col, "Cash And Cash Equivalents",
                                 "Cash Cash Equivalents And Short Term Investments")),
            "total_debt_b": to_b(_cell(df, col, "Total Debt")),
            "total_equity_b": to_b(_cell(df, col, "Stockholders Equity",
                                          "Total Equity Gross Minority Interest",
                                          "Common Stock Equity")),
            "total_assets_b": to_b(_cell(df, col, "Total Assets")),
            "net_debt_b": to_b(_cell(df, col, "Net Debt")),
        })
    return rows, []


def build_cashflow(tk):
    df = _stmt(tk, "cashflow", "cash_flow")
    if df is None:
        return [], ["cash flow unavailable"]
    rows = []
    for col in list(df.columns)[:6]:
        cfo = _cell(df, col, "Operating Cash Flow", "Total Cash From Operating Activities")
        capex = _cell(df, col, "Capital Expenditure", "Capital Expenditures")
        fcf = _cell(df, col, "Free Cash Flow")
        if fcf is None and cfo is not None and capex is not None:
            fcf = cfo + capex
        rows.append({
            "fy": _fy(col),
            "cfo_b": to_b(cfo),
            "capex_b": to_b(abs(capex)) if capex is not None else None,
            "fcf_b": to_b(fcf),
            "dividends_paid_b": to_b(_cell(df, col, "Cash Dividends Paid",
                                            "Common Stock Dividend Paid")),
            "buybacks_b": to_b(_cell(df, col, "Repurchase Of Capital Stock")),
            "debt_issuance_b": to_b(_cell(df, col, "Issuance Of Debt")),
            "debt_repayment_b": to_b(abs(_cell(df, col, "Repayment Of Debt"))
                                      if _cell(df, col, "Repayment Of Debt") is not None else None),
        })
    return rows, []


def build_returns(tk, jk_ticker):
    try:
        h = tk.history(period="1y", auto_adjust=True)
        if h is None or h.empty:
            return None, None
        last = float(h["Close"].iloc[-1])
        r1y = round((last / float(h["Close"].iloc[0]) - 1) * 100, 2)
        cy = h.index[-1].year
        hy = h[h.index.year == cy]
        ytd = round((last / float(hy["Close"].iloc[0]) - 1) * 100, 2) if not hy.empty else None
        return ytd, r1y
    except Exception:
        return None, None


def build_quarterly(tk, n=4):
    df = _stmt(tk, "quarterly_income_stmt", "quarterly_financials")
    rows = []
    if df is None:
        return rows
    for col in list(df.columns)[:n]:
        try:
            period = str(col.date())
        except Exception:
            period = str(col)
        rows.append({
            "period": period,
            "revenue_b": to_b(_cell(df, col, "Total Revenue", "Operating Revenue")),
            "net_income_b": to_b(_cell(df, col, "Net Income",
                                        "Net Income Common Stockholders")),
            "eps": num(_cell(df, col, "Diluted EPS", "Basic EPS")),
        })
    return rows


def compute_ratios(income, balance, cashflow):
    out = {}
    if income:
        i0 = income[0]
        rev = i0.get("revenue_b")
        ni = i0.get("net_income_b")
        if rev:
            if i0.get("gross_profit_b") is not None:
                out["gross_margin_pct"] = round(i0["gross_profit_b"] / rev * 100, 1)
            if i0.get("ebitda_b") is not None:
                out["ebitda_margin_pct"] = round(i0["ebitda_b"] / rev * 100, 1)
            if ni is not None:
                out["net_margin_pct"] = round(ni / rev * 100, 1)
    if cashflow and income:
        c0, i0 = cashflow[0], income[0]
        if c0.get("fcf_b") is not None and i0.get("revenue_b"):
            out["fcf_margin_pct"] = round(c0["fcf_b"] / i0["revenue_b"] * 100, 1)
        if c0.get("fcf_b") is not None and i0.get("net_income_b") not in (None, 0):
            out["fcf_conversion"] = round(c0["fcf_b"] / i0["net_income_b"], 2)
    if income and balance:
        i0, b0 = income[0], balance[0]
        if i0.get("net_income_b") is not None and b0.get("total_equity_b"):
            out["roe_pct"] = round(i0["net_income_b"] / b0["total_equity_b"] * 100, 1)
        if b0.get("total_debt_b") is not None and b0.get("total_equity_b"):
            out["debt_to_equity"] = round(b0["total_debt_b"] / b0["total_equity_b"], 2)
        if b0.get("total_assets_b") and i0.get("net_income_b"):
            out["roa_pct"] = round(i0["net_income_b"] / b0["total_assets_b"] * 100, 2)
    return out


# ---------- IDX filings ----------
def fetch_idx_filings(ticker_base):
    """Best-effort: IDX EFTS search for recent annual/quarterly reports."""
    filings = []
    gaps = []
    try:
        q = urllib.parse.quote(ticker_base)
        url = (f"https://efts.idx.co.id/LATEST/search-index?q={q}"
               "&documentType=&indexFrom=0&size=8&category=2")
        req = urllib.request.Request(url, headers={"User-Agent": IDX_UA})
        data = json.load(urllib.request.urlopen(req, timeout=12))
        hits = data.get("hits", {}).get("hits", [])
        for h in hits[:8]:
            src = h.get("_source", {})
            doc_type = src.get("documentType", "")
            url_doc = src.get("url") or src.get("file_path") or ""
            filings.append({
                "type": doc_type,
                "filed": src.get("date_modified") or src.get("submit_date"),
                "period": src.get("period") or src.get("year"),
                "url": url_doc,
            })
    except Exception as e:
        gaps.append(f"IDX EFTS filings fetch failed: {type(e).__name__}")
    return filings, gaps


# ---------- news ----------
def fetch_google_news(query, n=10):
    out = []
    try:
        url = ("https://news.google.com/rss/search?q="
               + urllib.parse.quote(query)
               + "&hl=en-US&gl=ID&ceid=ID:en")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AtlasResearch/1.0; +algothinks@gmail.com)"},
        )
        xml_bytes = urllib.request.urlopen(req, timeout=15).read()
        root = ET.fromstring(xml_bytes)
        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue
            src = item.find("source")
            out.append({
                "title": title,
                "publisher": src.text if src is not None else None,
                "url": item.findtext("link"),
                "date": item.findtext("pubDate"),
            })
            if len(out) >= n:
                break
    except Exception:
        pass
    return out


def fetch_rec_trend(tk):
    try:
        df = tk.recommendations
        if df is not None and not df.empty:
            row = df.iloc[0].to_dict()
            return {k: int(row[k]) for k in
                    ("strongBuy", "buy", "hold", "sell", "strongSell")
                    if k in row and row[k] == row[k]}
    except Exception:
        pass
    return {}


def fetch_holders(tk):
    out = {}
    try:
        mh = tk.major_holders
        if mh is not None and not mh.empty:
            for label, key in (
                ("insidersPercentHeld", "insider_pct"),
                ("institutionsPercentHeld", "institutional_pct"),
            ):
                if label in mh.index:
                    out[key] = round(float(mh.loc[label].iloc[0]) * 100, 2)
    except Exception:
        pass
    return out


def fetch_earnings_date(tk):
    try:
        cal = tk.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed and isinstance(ed, (list, tuple)) and len(ed) > 0:
                return str(ed[0])
            elif ed:
                return str(ed)
    except Exception:
        pass
    return None


# ---------- IDX peers (major Indonesian consumer finance / multifinance) ----------
ID_SECTOR_PEERS = {
    "BFIN": ["ADMF.JK", "MFIN.JK", "CFIN.JK", "BBRI.JK"],   # consumer finance comps + BBRI as bank anchor
    "BBRI": ["BMRI.JK", "BBCA.JK", "BBNI.JK", "BFIN.JK"],
    "BBCA": ["BMRI.JK", "BBRI.JK", "BBNI.JK", "BNGA.JK"],
    "BMRI": ["BBRI.JK", "BBCA.JK", "BBNI.JK", "BNGA.JK"],
}


def fetch_peers(peers):
    out = []
    for p in peers:
        info = {}
        try:
            # Peers may already have .JK or not
            ticker_jk = _jk(p.replace(".JK", "")) if not p.endswith(".JK") else p
            info = yf.Ticker(ticker_jk).get_info()
        except Exception:
            pass
        out.append({
            "ticker": p,
            "name": info.get("shortName") or p,
            "pe_ntm": num(info.get("forwardPE")),
            "pe_ttm": num(info.get("trailingPE")),
            "pb": num(info.get("priceToBook")),
            "roe_pct": pct(info.get("returnOnEquity")),
            "div_yield_pct": pct(info.get("dividendYield")),
            "y1": pct(info.get("52WeekChange")),
        })
    return out


# ---------- main fetch ----------
def fetch(ticker, out=None, do_idx=True):
    ticker_base = ticker.upper().replace(".JK", "")
    ticker_jk = _jk(ticker_base)
    gaps = []

    tk = yf.Ticker(ticker_jk)

    info = {}
    try:
        info = tk.get_info()
    except Exception:
        try:
            info = tk.info
        except Exception:
            gaps.append("yfinance .info unavailable")
    try:
        fi = tk.fast_info
    except Exception:
        fi = {}

    income, g1 = build_income(tk)
    balance, g2 = build_balance(tk)
    cashflow, g3 = build_cashflow(tk)
    gaps += g1 + g2 + g3

    def _nonempty(rows):
        return [r for r in rows if any(v is not None for k, v in r.items() if k not in ("fy", "period"))]

    income = _nonempty(income)
    balance = _nonempty(balance)
    cashflow = _nonempty(cashflow)

    ytd, r1y = build_returns(tk, ticker_jk)

    net_debt_b = None
    if balance:
        nd = balance[0].get("net_debt_b")
        if nd is not None:
            net_debt_b = nd
        else:
            td, cash = balance[0].get("total_debt_b"), balance[0].get("cash_b")
            if td is not None and cash is not None:
                net_debt_b = round(td - cash, 3)

    cur_px = _fget(fi, "last_price", "lastPrice") or num(info.get("currentPrice") or info.get("regularMarketPrice"))
    dps = num(info.get("dividendRate"))
    div_yield_pct = round(dps / cur_px * 100, 2) if (dps and cur_px) else num(info.get("dividendYield")) and round(num(info.get("dividendYield")) * 100, 2)
    if div_yield_pct is None:
        dy = num(info.get("dividendYield"))
        div_yield_pct = round(dy * 100, 2) if dy else None

    adtv_m = None
    vol = num(info.get("averageDailyVolume10Day"))
    if vol and cur_px:
        adtv_m = round(vol * cur_px / 1e9, 3)   # IDR billions (not USD millions)

    filings, g_idx = [], []
    if do_idx:
        filings, g_idx = fetch_idx_filings(ticker_base)
        gaps += g_idx

    if not income:
        gaps.append("annual financials empty (yfinance rate limit or delisted?)")

    ts = nz.now_utc()
    sources = [{"name": "yfinance", "fetched_utc": nz.iso(ts), "ticker_queried": ticker_jk}]
    if filings:
        sources.append({"name": "IDX EFTS", "fetched_utc": nz.iso(ts)})

    bundle = {
        "_meta": {
            "ticker": ticker_base,
            "snapshot_id": nz.snapshot_id(ticker_base, ts),
            "as_of_utc": nz.iso(ts),
            "market": "ID",
            "currency": "IDR",
            "adapter": "hermes/id",
            "sources": sources,
            "gaps": gaps,
            "notes": "Money fields in IDR billions (_b). 1 IDR T = 1,000 IDR B.",
        },
        "profile": {
            "name": info.get("longName") or info.get("shortName") or ticker_base,
            "ticker_jk": ticker_jk,
            "listings": "IDX",
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": "Indonesia",
            "description": info.get("longBusinessSummary"),
            "employees": num(info.get("fullTimeEmployees")),
            "business_type_hint": biz_hint(info.get("sector"), info.get("industry")),
            "regulator": "OJK",          # Otoritas Jasa Keuangan — Indonesia's FSA
        },
        "price": {
            "current": cur_px,
            "currency": "IDR",
            "high_52w": _fget(fi, "year_high", "yearHigh") or num(info.get("fiftyTwoWeekHigh")),
            "low_52w": _fget(fi, "year_low", "yearLow") or num(info.get("fiftyTwoWeekLow")),
            "ma50": _fget(fi, "fifty_day_average", "fiftyDayAverage") or num(info.get("fiftyDayAverage")),
            "ma200": _fget(fi, "two_hundred_day_average", "twoHundredDayAverage") or num(info.get("twoHundredDayAverage")),
            "ytd_pct": ytd,
            "return_1y_pct": r1y,
            "beta": num(info.get("beta")),
        },
        "market_stats": {
            "market_cap_b": to_b(_fget(fi, "market_cap", "marketCap") or info.get("marketCap")),
            "enterprise_value_b": to_b(info.get("enterpriseValue")),
            "shares_outstanding_b": to_b(_fget(fi, "shares") or info.get("sharesOutstanding")),
            "net_debt_b": net_debt_b,
            "adtv_idr_b": adtv_m,       # IDR billions per day
            "dividend_per_share_idr": dps,
            "dividend_yield_pct": div_yield_pct,
        },
        "valuation_multiples": {
            "pe_ttm": num(info.get("trailingPE")),
            "pe_ntm": num(info.get("forwardPE")),
            "ev_ebitda_ttm": num(info.get("enterpriseToEbitda")),
            "ev_sales_ttm": num(info.get("enterpriseToRevenue")),
            "pb": num(info.get("priceToBook")),
            "peg": num(info.get("trailingPegRatio") or info.get("pegRatio")),
            "roe_pct": pct(info.get("returnOnEquity")),
            "roa_pct": pct(info.get("returnOnAssets")),
        },
        "financials": {"income": income, "balance": balance, "cashflow": cashflow},
        "estimates": {
            "eps_ntm": num(info.get("forwardEps")),
            "eps_ttm": num(info.get("trailingEps")),
            "target_mean": num(info.get("targetMeanPrice")),
            "target_median": num(info.get("targetMedianPrice")),
            "target_high": num(info.get("targetHighPrice")),
            "target_low": num(info.get("targetLowPrice")),
            "num_analysts": num(info.get("numberOfAnalystOpinions")),
            "rec_mean": num(info.get("recommendationMean")),
            "recommendation_key": info.get("recommendationKey"),
        },
        "peers": [],
        "segments": [],
        "filings": filings,
    }

    bundle["earnings_date"] = fetch_earnings_date(tk)
    news = fetch_google_news(f"{ticker_base} BFI Finance Indonesia saham")
    if not news:
        news = fetch_google_news(f"{ticker_base} Indonesia stock")
    bundle["news"] = news
    bundle["recommendation_trend"] = fetch_rec_trend(tk)
    bundle["holders"] = fetch_holders(tk)
    bundle["quarterly"] = build_quarterly(tk)
    bundle["ratios"] = compute_ratios(income, balance, cashflow)

    peers_list = ID_SECTOR_PEERS.get(ticker_base, [])
    if peers_list:
        bundle["peers"] = fetch_peers(peers_list)

    if not bundle["news"]:
        bundle["_meta"]["gaps"].append("news feed empty (Google News blocked or no results)")

    return nz.write_bundle(bundle, out)


def main():
    ap = argparse.ArgumentParser(description="Hermes ID adapter — Indonesian IDX stocks")
    ap.add_argument("--ticker", required=True, help="IDX ticker (e.g. BFIN, not BFIN.JK)")
    ap.add_argument("--out", default=None, help="output path (default output/<T>/<T>_databundle.json)")
    ap.add_argument("--no-idx", action="store_true", help="skip the IDX filing call (offline)")
    args = ap.parse_args()
    path = fetch(args.ticker, out=args.out, do_idx=not args.no_idx)
    print(f"[hermes/id] wrote {path}")


if __name__ == "__main__":
    main()
