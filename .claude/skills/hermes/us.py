"""Hermes US adapter — fetch and freeze a data bundle for a US-listed ticker.

Sources:
  - yfinance : price, market stats, multiples, annual financials, estimates
  - SEC EDGAR: recent 10-K / 10-Q / 8-K filing pointers

Writes output/<T>/<T>_databundle.json (BUNDLE_SCHEMA.md). Defensive by design: any field a
source doesn't provide is omitted and logged to _meta.gaps, never invented.

Usage:
    python us.py --ticker AVGO
    python us.py --ticker AVGO --out "C:/.../Atlas/output/AVGO/AVGO_databundle.json"
    python us.py --ticker AVGO --no-sec          # skip the SEC call (offline)
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import normalize as nz

try:
    import yfinance as yf
except ImportError:
    sys.exit("ERROR: yfinance not installed. Run: pip install yfinance")

SEC_UA = "Atlas Research algothinks@gmail.com"


# ---------- safe coercion ----------
def num(x):
    try:
        f = float(x)
        return None if f != f else f          # NaN guard
    except (TypeError, ValueError):
        return None


def to_b(x):
    f = num(x)
    return round(f / 1e9, 3) if f is not None else None


def pct(x):
    f = num(x)
    return round(f * 100, 2) if f is not None else None


# ---------- yfinance helpers ----------
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
    if "bank" in i:
        return "bank"
    if "insurance" in i:
        return "insurer"
    if "asset management" in i or "capital markets" in i:
        return "asset_manager"
    if "reit" in i or "real estate" in s:
        return "reit"
    if any(k in i for k in ["oil", "gas", "mining", "metals", "coal", "gold"]):
        return "miner_ep"
    if "software" in i or "software" in s or "internet" in i:
        return "software"
    if "semiconductor" in i:
        return "industrial"          # DCF default; Daedalus upgrades to conglomerate if multi-segment
    if "telecom" in i or "utilit" in i:
        return "telecom_utility"
    if any(k in s for k in ["consumer", "retail"]):
        return "consumer"
    return "industrial"


def build_income(tk):
    df = _stmt(tk, "income_stmt", "financials")
    if df is None:
        return [], ["income statement unavailable"]
    rows = []
    for col in list(df.columns)[:6]:
        rows.append({
            "fy": _fy(col),
            "revenue_b": to_b(_cell(df, col, "Total Revenue", "TotalRevenue")),
            "gross_profit_b": to_b(_cell(df, col, "Gross Profit")),
            "ebit_b": to_b(_cell(df, col, "Operating Income", "EBIT")),
            "ebitda_b": to_b(_cell(df, col, "EBITDA", "Normalized EBITDA")),
            "net_income_b": to_b(_cell(df, col, "Net Income", "Net Income Common Stockholders")),
            "eps": num(_cell(df, col, "Diluted EPS", "Basic EPS")),
            "shares_b": to_b(_cell(df, col, "Diluted Average Shares", "Basic Average Shares")),
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
                                          "Total Equity Gross Minority Interest")),
            "total_assets_b": to_b(_cell(df, col, "Total Assets")),
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
            fcf = cfo + capex                 # capex is reported negative in yfinance
        rows.append({
            "fy": _fy(col),
            "cfo_b": to_b(cfo),
            "capex_b": to_b(abs(capex)) if capex is not None else None,
            "fcf_b": to_b(fcf),
            "dividends_paid_b": to_b(_cell(df, col, "Cash Dividends Paid", "Common Stock Dividend Paid")),
            "buybacks_b": to_b(_cell(df, col, "Repurchase Of Capital Stock")),
        })
    return rows, []


def build_returns(tk):
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


def fetch_sec(ticker):
    """Best-effort: map ticker -> CIK, then pull recent 10-K/10-Q/8-K pointers."""
    try:
        req = urllib.request.Request("https://www.sec.gov/files/company_tickers.json",
                                     headers={"User-Agent": SEC_UA})
        data = json.load(urllib.request.urlopen(req, timeout=20))
        cik = None
        for row in data.values():
            if row.get("ticker", "").upper() == ticker.upper():
                cik = str(row["cik_str"]).zfill(10)
                break
        if not cik:
            return None, [], ["SEC: ticker not found in EDGAR map"]
        req2 = urllib.request.Request(f"https://data.sec.gov/submissions/CIK{cik}.json",
                                      headers={"User-Agent": SEC_UA})
        sub = json.load(urllib.request.urlopen(req2, timeout=20))
        recent = sub.get("filings", {}).get("recent", {})
        forms, dates = recent.get("form", []), recent.get("filingDate", [])
        accns, docs = recent.get("accessionNumber", []), recent.get("primaryDocument", [])
        out = []
        for i in range(len(forms)):
            if forms[i] in ("10-K", "10-Q", "8-K"):
                accn = accns[i].replace("-", "")
                out.append({
                    "type": forms[i], "filed": dates[i],
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{docs[i]}",
                })
                if len(out) >= 8:
                    break
        return cik, out, []
    except Exception as e:
        return None, [], [f"SEC fetch failed: {type(e).__name__}"]


SECTOR_PEERS = {
    "AVGO": ["NVDA", "MRVL", "QCOM", "TXN", "AMD"],
    "NVDA": ["AVGO", "AMD", "MRVL", "TSM", "QCOM"],
    "AMD": ["NVDA", "INTC", "AVGO", "QCOM", "MRVL"],
}


def fetch_edgar_facts(cik):
    """SEC EDGAR companyfacts -> authoritative consolidated us-gaap line items by fiscal year.
    Resolves the yfinance reconciliation gaps and adds interest/goodwill/receivables/stock-comp/debt."""
    from datetime import date
    out = {"by_fy": {}, "gaps": []}
    try:
        req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                                     headers={"User-Agent": SEC_UA})
        data = json.load(urllib.request.urlopen(req, timeout=40))
    except Exception as e:
        out["gaps"].append(f"EDGAR companyfacts failed: {type(e).__name__}")
        return out
    gaap = data.get("facts", {}).get("us-gaap", {})
    CONCEPTS = {
        "revenue_b": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        "net_income_b": ["NetIncomeLoss"],
        "operating_income_b": ["OperatingIncomeLoss"],
        "interest_expense_b": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
        "goodwill_b": ["Goodwill"],
        "intangibles_b": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
        "receivables_b": ["AccountsReceivableNetCurrent"],
        "stock_comp_b": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
        "long_term_debt_b": ["LongTermDebtNoncurrent", "LongTermDebt"],
        "cash_b": ["CashAndCashEquivalentsAtCarryingValue"],
    }

    def annual(tags):
        for tag in tags:
            node = gaap.get(tag)
            if not node:
                continue
            for unit, facts in node.get("units", {}).items():
                res = {}
                for f in facts:
                    if not str(f.get("form", "")).startswith("10-K"):
                        continue
                    if f.get("fp") != "FY" or f.get("fy") is None:
                        continue
                    s, e = f.get("start"), f.get("end")
                    if s and e:
                        try:
                            sy, sm, sd = map(int, s.split("-")); ey, em, ed = map(int, e.split("-"))
                            if (date(ey, em, ed) - date(sy, sm, sd)).days < 300:
                                continue
                        except Exception:
                            pass
                    res[int(f["fy"])] = f.get("val")
                if res:
                    return res
        return {}

    raw, fys = {}, set()
    for key, tags in CONCEPTS.items():
        raw[key] = annual(tags)
        fys.update(raw[key].keys())
    for fy in sorted(fys, reverse=True)[:6]:
        out["by_fy"][str(fy)] = {k: (round(raw[k][fy] / 1e9, 3) if fy in raw[k] and raw[k][fy] is not None else None)
                                 for k in CONCEPTS}
    return out


def fetch_filing_excerpts(filings):
    """Fetch the latest 10-Q/10-K primary doc, strip to text, and pull keyword windows for the
    narrative items (segments, customer concentration, debt maturities) the agents then parse."""
    import re as _re
    target = next((f for f in filings if f.get("type") in ("10-Q", "10-K")), None)
    if not target:
        return {}
    try:
        req = urllib.request.Request(target["url"], headers={"User-Agent": SEC_UA})
        html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    except Exception as e:
        return {"error": f"filing fetch failed: {type(e).__name__}"}
    text = _re.sub(r"<[^>]+>", " ", html)
    text = _re.sub(r"&#?[a-zA-Z0-9]+;", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    keywords = ["Infrastructure software", "Semiconductor solutions", "Net revenue by",
                "largest customer", "of our net revenue", "of net revenue", "maturities of",
                "Stock-based compensation", "Interest expense"]
    excerpts = {}
    low = text.lower()
    for kw in keywords:
        i = low.find(kw.lower())
        if i >= 0:
            excerpts[kw] = text[max(0, i - 150):i + 450]
    return {"source": target["url"], "type": target["type"], "filed": target.get("filed"), "excerpts": excerpts}


def fetch_peers(peers):
    out = []
    for p in peers:
        info = {}
        try:
            info = yf.Ticker(p).get_info()
        except Exception:
            pass
        out.append({
            "ticker": p, "name": info.get("shortName") or p,
            "pe_ntm": num(info.get("forwardPE")), "ev_ebitda": num(info.get("enterpriseToEbitda")),
            "rev_growth_ttm": pct(info.get("revenueGrowth")),
            "ytd": None, "y1": pct(info.get("52WeekChange")),
        })
    return out


def fetch_forward_eps(tk):
    try:
        df = tk.earnings_estimate
        if df is not None and not df.empty:
            for period in ("+1y", "0y"):
                if period in df.index and "avg" in df.columns:
                    v = num(df.loc[period, "avg"])
                    if v:
                        return v, period
    except Exception:
        pass
    return None, None


def fetch_google_news(query, n=12):
    """Free, no key: Google News RSS for the ticker. Real, ticker-specific headlines + sources + links."""
    import xml.etree.ElementTree as ET
    import urllib.parse
    out = []
    try:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AtlasResearch/1.0; +algothinks@gmail.com)"})
        xml = urllib.request.urlopen(req, timeout=25).read()
        root = ET.fromstring(xml)
        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue
            src = item.find("source")
            out.append({"title": title, "publisher": src.text if src is not None else None,
                        "url": item.findtext("link"), "date": item.findtext("pubDate")})
            if len(out) >= n:
                break
    except Exception:
        pass
    return out


def fetch_stocktwits(ticker):
    """Free: Stocktwits message stream -> live bull/bear sentiment + recent messages."""
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AtlasResearch/1.0)"})
        data = json.load(urllib.request.urlopen(req, timeout=25))
        msgs = data.get("messages", [])
        bull = bear = 0
        recent = []
        for m in msgs:
            s = ((m.get("entities") or {}).get("sentiment") or {}).get("basic")
            if s == "Bullish":
                bull += 1
            elif s == "Bearish":
                bear += 1
            if len(recent) < 5 and m.get("body"):
                recent.append(m["body"][:200])
        tagged = bull + bear
        return {"source": "stocktwits", "message_count": len(msgs), "tagged_messages": tagged,
                "bullish_pct": round(bull / tagged * 100, 1) if tagged else None,
                "bearish_pct": round(bear / tagged * 100, 1) if tagged else None, "recent": recent}
    except Exception as e:
        return {"source": "stocktwits", "error": type(e).__name__}


def fetch_news(tk, n=6):
    out = []
    try:
        for item in (tk.news or []):
            c = item.get("content", item) if isinstance(item, dict) else {}
            title = c.get("title") or (item.get("title") if isinstance(item, dict) else None)
            if not title:
                continue
            prov = c.get("provider")
            pub = prov.get("displayName") if isinstance(prov, dict) else (item.get("publisher") if isinstance(item, dict) else None)
            cu = c.get("canonicalUrl")
            link = cu.get("url") if isinstance(cu, dict) else (item.get("link") if isinstance(item, dict) else None)
            out.append({"title": title, "publisher": pub, "url": link, "date": c.get("pubDate") or c.get("displayTime")})
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
            return {k: int(row[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell") if k in row and row[k] == row[k]}
    except Exception:
        pass
    return {}


def fetch_holders(tk):
    out = {}
    try:
        mh = tk.major_holders
        if mh is not None and not mh.empty:
            for label, key in (("insidersPercentHeld", "insider_pct"), ("institutionsPercentHeld", "institutional_pct")):
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
            if ed:
                return str(ed[0]) if isinstance(ed, (list, tuple)) else str(ed)
    except Exception:
        pass
    return None


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
        rows.append({"period": period,
                     "revenue_b": to_b(_cell(df, col, "Total Revenue")),
                     "net_income_b": to_b(_cell(df, col, "Net Income", "Net Income Common Stockholders")),
                     "eps": num(_cell(df, col, "Diluted EPS", "Basic EPS"))})
    return rows


def compute_ratios(income, balance, cashflow):
    out = {}
    if income:
        i0 = income[0]
        rev = i0.get("revenue_b")
        if rev:
            if i0.get("gross_profit_b") is not None:
                out["gross_margin_pct"] = round(i0["gross_profit_b"] / rev * 100, 1)
            if i0.get("ebitda_b") is not None:
                out["ebitda_margin_pct"] = round(i0["ebitda_b"] / rev * 100, 1)
            if i0.get("net_income_b") is not None:
                out["net_margin_pct"] = round(i0["net_income_b"] / rev * 100, 1)
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
    return out


def fetch(ticker, out=None, do_sec=True):
    ticker = ticker.upper()
    tk = yf.Ticker(ticker)
    gaps = []

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
        return [r for r in rows if any(v is not None for k, v in r.items() if k != "fy")]
    income, balance, cashflow = _nonempty(income), _nonempty(balance), _nonempty(cashflow)

    ytd, r1y = build_returns(tk)

    # net debt from the latest balance sheet if possible
    net_debt_b = None
    if balance:
        td, cash = balance[0].get("total_debt_b"), balance[0].get("cash_b")
        if td is not None and cash is not None:
            net_debt_b = round(td - cash, 3)

    cur_px = _fget(fi, "last_price", "lastPrice") or num(info.get("currentPrice"))
    dps = num(info.get("dividendRate"))
    div_yield_pct = round(dps / cur_px * 100, 2) if (dps and cur_px) else None

    adtv_m = None
    vol = num(info.get("averageDailyVolume10Day"))
    if vol and cur_px:
        adtv_m = round(vol * cur_px / 1e6, 1)

    cik, filings, gsec = (None, [], [])
    if do_sec:
        cik, filings, gsec = fetch_sec(ticker)
        gaps += gsec

    if not income:
        gaps.append("annual financials empty (yfinance rate limit or delisted?)")
    gaps.append("segment revenue: see filing_excerpts (parse the 10-Q segment note); not in structured yfinance data")

    ts = nz.now_utc()
    sources = [{"name": "yfinance", "fetched_utc": nz.iso(ts)}]
    if cik:
        sources.append({"name": "SEC EDGAR", "fetched_utc": nz.iso(ts), "cik": cik})

    bundle = {
        "_meta": {
            "ticker": ticker,
            "snapshot_id": nz.snapshot_id(ticker, ts),
            "as_of_utc": nz.iso(ts),
            "market": "US",
            "currency": (getattr(fi, "currency", None) or info.get("currency") or "USD"),
            "adapter": "hermes/us",
            "sources": sources,
            "gaps": gaps,
        },
        "profile": {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "listings": info.get("exchange") or "US",
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country") or "US",
            "description": info.get("longBusinessSummary"),
            "employees": num(info.get("fullTimeEmployees")),
            "business_type_hint": biz_hint(info.get("sector"), info.get("industry")),
        },
        "price": {
            "current": cur_px,
            "currency": (getattr(fi, "currency", None) or info.get("currency") or "USD"),
            "high_52w": _fget(fi, "year_high", "yearHigh"),
            "low_52w": _fget(fi, "year_low", "yearLow"),
            "ma50": _fget(fi, "fifty_day_average", "fiftyDayAverage"),
            "ma200": _fget(fi, "two_hundred_day_average", "twoHundredDayAverage"),
            "ytd_pct": ytd,
            "return_1y_pct": r1y,
            "beta": num(info.get("beta")),
        },
        "market_stats": {
            "market_cap_b": to_b(_fget(fi, "market_cap", "marketCap") or info.get("marketCap")),
            "enterprise_value_b": to_b(info.get("enterpriseValue")),
            "shares_outstanding_b": to_b(_fget(fi, "shares") or info.get("sharesOutstanding")),
            "net_debt_b": net_debt_b,
            "adtv_usd_m": adtv_m,
            "dividend_per_share": dps,
            "dividend_yield_pct": div_yield_pct,
        },
        "valuation_multiples": {
            "pe_ttm": num(info.get("trailingPE")),
            "pe_ntm": num(info.get("forwardPE")),
            "ev_ebitda_ttm": num(info.get("enterpriseToEbitda")),
            "ev_sales_ttm": num(info.get("enterpriseToRevenue")),
            "pb": num(info.get("priceToBook")),
            "peg": num(info.get("trailingPegRatio") or info.get("pegRatio")),
        },
        "financials": {"income": income, "balance": balance, "cashflow": cashflow},
        "estimates": {
            "eps_ntm": num(info.get("forwardEps")),
            "target_mean": num(info.get("targetMeanPrice")),
            "target_median": num(info.get("targetMedianPrice")),
            "num_analysts": num(info.get("numberOfAnalystOpinions")),
            "rec_mean": num(info.get("recommendationMean")),
        },
        "peers": [],
        "segments": [],
        "filings": filings,
    }
    bundle["earnings_date"] = fetch_earnings_date(tk)
    gnews = fetch_google_news(f"{ticker} {bundle['profile'].get('name', '')} stock")
    bundle["news"] = gnews if gnews else fetch_news(tk)
    bundle["social_sentiment"] = fetch_stocktwits(ticker)
    bundle["recommendation_trend"] = fetch_rec_trend(tk)
    bundle["holders"] = fetch_holders(tk)
    bundle["quarterly"] = build_quarterly(tk)
    bundle["ratios"] = compute_ratios(income, balance, cashflow)
    bundle["estimates"]["target_high"] = num(info.get("targetHighPrice"))
    bundle["estimates"]["target_low"] = num(info.get("targetLowPrice"))
    bundle["estimates"]["recommendation_key"] = info.get("recommendationKey")
    fe, fe_period = fetch_forward_eps(tk)
    bundle["estimates"]["eps_ntm_consensus"] = fe
    bundle["estimates"]["eps_ntm_consensus_period"] = fe_period
    if cik:
        bundle["edgar"] = fetch_edgar_facts(cik)
        bundle["filing_excerpts"] = fetch_filing_excerpts(filings)
    else:
        bundle["edgar"] = {"gaps": ["no CIK; EDGAR not fetched"]}
    peers_list = SECTOR_PEERS.get(ticker, [])
    if peers_list:
        bundle["peers"] = fetch_peers(peers_list)
    if not bundle["news"]:
        bundle["_meta"]["gaps"].append("news feed empty from yfinance")
    return nz.write_bundle(bundle, out)


def main():
    ap = argparse.ArgumentParser(description="Hermes US data adapter")
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--out", default=None, help="output path (default output/<T>/<T>_databundle.json)")
    ap.add_argument("--no-sec", action="store_true", help="skip the SEC EDGAR call")
    args = ap.parse_args()
    path = fetch(args.ticker, out=args.out, do_sec=not args.no_sec)
    print(f"[hermes/us] wrote {path}")


if __name__ == "__main__":
    main()
