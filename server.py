#!/usr/bin/env python3
"""japan-stock-mcp: J-Quants API for AI agents — live screener, quotes, valuation, calendar.

Retrieves Japanese equity data from the official J-Quants API (JPX):
  • Latest daily OHLCV for any TSE-listed stock
  • Screener: filter by market tier, sector, min mkt-cap, volatility bands, price-change
  • Valuation metrics: P/E, P/B, dividend yield, market cap
  • Financial summary (Sales / Operating / Net Income — latest quarter)
  • Trading calendar & sector code mapping

Free-tier plan: 12-week lookback lag. Auth via JQUANTS_API_KEY env var.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

mcp = FastMCP("japan-stock-mcp")

API_BASE = "https://api.jquants.com/v2"
API_KEY_ENV = "JQUANTS_API_KEY"

SECTOR_33 = {
    "0100": "農業・鉱業", "0200": "建設業", "0300": "情報・通信", "0400": "金融・保険業",
    "0500": "小売業", "0600": "卸売業", "0700": "運輸・郵便業", "0800": "電気・ガス・熱供給・水道業",
    "0900": "化学産業", "1000": "石油・石炭製品", "1100": "ゴム製品", "1200": "鉄道運送業",
    "1300": "鉄鋼業", "1400": "非鉄金属", "1500": "機械産業", "1600": "船・橋梁業",
    "1700": "事務用機械", "1800": "電機", "1900": "医薬品", "2000": "食料品",
    "2100": "繊維", "2200": "_paper・パルプ", "2300": " paper・建材・プラスチック",
    "2400": "印刷・製本", "2500": "他の製品", "2600": "その他製造業",
    "2700": "サービス業", "2800": "不動産業", "2900": "業種不明",
}

MARKET_MAP = {
    "0111": "プライム",
    "0121": "スタンダード",
    "0131": "グロース",
    "0141": "エクスクルーシブ",
    "0211": "マザーズ",
    "0311": "ジャスダック",
    "0411": "REIT",
    "0511": "上場廃止",
}

S33_SECTOR_FILTER = {
    "bank": "0400", "insurance": "0400", "finance": "0400",
    "it": "0300", "tech": "0300", "info": "0300", "communication": "0300",
    "retail": "0500", "wholesale": "0600", "logistics": "0700",
    "energy": "0800", "chemical": "0900", "iron": "1300",
    "machinery": "1500", "auto": "1600",
    "electric": "1800", "pharma": "1900", "food": "2000",
    "construction": "0200", "real_estate": "2800", "service": "2700",
}


def _api_key() -> str:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV} not set. Get a free key at https://jpx-jquants.com — see README."
        )
    return key


def _req(path: str, params: Optional[Dict[str, str]] = None) -> Any:
    url = API_BASE + path
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    full = url + qs
    headers = {"x-api-key": _api_key()}
    req = urllib.request.Request(full, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"J-Quants {e.code}: {body[:400]}")


# ─── core tools ──────────────────────────────────────────────────────────────


@mcp.tool()
async def get_quote(code: str, days: int = 5) -> Dict[str, Any]:
    """Latest daily OHLCV for a TSE stock.

    Args:
        code: 3- or 5-digit TSE stock code (e.g. "6758" for Sony, "7203" for Toyota).
              4-digit codes are zero-padded; 3-digit codes are accepted as-is.
        days: How many trading days to return (default 5, max 504 ≈ 2yr free-limit).
    Returns:
        {code, name, sector, market, history: [{date, O, H, L, C, Vo, Va, AdjC, AdjVo}]}
    """
    code5 = code.zfill(5)
    bars = _api_req("/equities/bars/daily", {"code": code5})
    rows = bars.get("data", [])
    rows.sort(key=lambda r: r.get("Date", ""), reverse=True)
    items = []
    for r in rows[:days]:
        items.append({
            "date": r.get("Date"),
            "O": r.get("O"), "H": r.get("H"),
            "L": r.get("L"), "C": r.get("C"),
            "Vo": r.get("Vo"), "Va": r.get("Va"),
            "AdjC": r.get("AdjC"), "AdjVo": r.get("AdjVo"),
        })
    # Master record for name/market
    master = _api_req("/equities/master", {"code": code5})
    rec = master["data"][0] if master.get("data") else {}
    return {
        "code": code5,
        "name": rec.get("CoName"),
        "name_en": rec.get("CoNameEn"),
        "sector_17": rec.get("S17Nm"),
        "sector_33": rec.get("S33Nm"),
        "market": rec.get("MktNm"),
        "history": items,
    }


@mcp.tool()
async def screener(
    market: Optional[str] = None,
    sector: Optional[str] = None,
    min_market_cap: Optional[int] = None,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    day_change_gte: Optional[float] = None,
    day_change_lte: Optional[float] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Screen TSE-listed equities with filters on market, sector, price, and change.

    All filters are optional — provide any subset. Results sorted by market cap descending.

    Args:
        market: "prime"/"standard"/"growth" (mapped to JPX market codes).
        sector: Japanese keyword or English alias (e.g. "bank", "it", "food", "pharma").
        min_market_cap: Minimum market cap in million JPY (e.g. 500000 = 50B).
        max_price / min_price: Price range in JPY.
        day_change_gte / day_change_lte: Min/max single-day change percentage.
        limit: Max rows returned (default 20, max 500).
    Returns:
        {filters_applied, count, rows: [{code, name, market, sector, price, change_pct, mkt_cap}]}
    """
    # Resolve sector code
    s33_code = None
    if sector:
        low = sector.lower()
        s33_code = S33_SECTOR_FILTER.get(low)
        if not s33_code:
            # Try partial match against sector names
            for k, v in S33_SECTOR_FILTER.items():
                if k in low or low in k:
                    s33_code = v
                    break

    # Resolve market code
    mkt_code = None
    if market:
        low = market.lower()
        if low in ("prime",):
            mkt_code = "0111"
        elif low in ("standard", "std"):
            mkt_code = "0121"
        elif low in ("growth",):
            mkt_code = "0131"
        elif low in ("matters", "mother",):
            mkt_code = "0211"

    # Fetch master list (free: last 12 weeks)
    master = _api_req("/equities/master", {})
    all_records = master.get("data", [])

    # Fetch latest bars in batch (date-only query — returns all listed as of today)
    today = date.today().isoformat()
    try:
        bars_resp = _api_req("/equities/bars/daily", {"date": today})
        bars_map: Dict[str, Dict] = {r.get("Code", ""): r for r in bars_resp.get("data", [])}
    except Exception:
        # free plan may not support broad date query beyond lag window; fall back to per-code
        bars_map = {}

    # Fetch valuations for scoring
    val_map: Dict[str, Dict] = {}
    try:
        val_resp = _api_req("/equities/valuation", {})
        for r in val_resp.get("data", []):
            val_map[r.get("Code", "")] = r
    except Exception:
        pass

    # Filter
    def _match(rec):
        code5 = rec.get("Code", "")
        if mkt_code and rec.get("Mkt") != mkt_code:
            return False
        if s33_code and rec.get("S33") != s33_code:
            return False
        val = val_map.get(code5, {})
        mkt_cap = val.get("MktCap")
        if min_market_cap and (mkt_cap is None or mkt_cap < min_market_cap):
            return False
        bar = bars_map.get(code5, {})
        price = bar.get("C")
        adj_c = bar.get("AdjC", price)
        if min_price and (adj_c is None or adj_c < min_price):
            return False
        if max_price and (adj_c is None or adj_c > max_price):
            return False
        return True

    matched = [r for r in all_records if _match(r)]

    # Score & sort by mkt cap desc, apply limit
    scored = []
    for r in matched:
        code5 = r.get("Code", "")
        val = val_map.get(code5, {})
        bar = bars_map.get(code5, {})
        price = bar.get("C") or val.get("PrevC")
        mkt_cap = val.get("MktCap")
        prev_close = val.get("PrevC")
        chg_pct = None
        if prev_close and price and prev_close > 0:
            chg_pct = round((price - prev_close) / prev_close * 100, 2)
        if day_change_gte is not None and (chg_pct is None or chg_pct < day_change_gte):
            continue
        if day_change_lte is not None and (chg_pct is None or chg_pct > day_change_lte):
            continue
        scored.append({
            "code": code5,
            "name": r.get("CoName"),
            "name_en": r.get("CoNameEn"),
            "market": r.get("MktNm"),
            "sector": r.get("S33Nm"),
            "price": price,
            "change_pct": chg_pct,
            "mkt_cap_m": mkt_cap,
        })

    scored.sort(key=lambda x: (x.get("mkt_cap_m") or 0), reverse=True)
    scored = scored[:limit]

    return {
        "filters": {
            "market": market,
            "sector": sector,
            "min_market_cap_m": min_market_cap,
            "price_range": [min_price, max_price],
            "change_pct_range": [day_change_gte, day_change_lte],
        },
        "count_before_limit": len(matched),
        "count": len(scored),
        "rows": scored,
        "note": "Free plan: 12-week data lag; sector/market filters use current master snapshot.",
    }


@mcp.tool()
async def get_valuation(code: str) -> Dict[str, Any]:
    """Valuation snapshot: market cap, P/E, P/B, dividend yield for a TSE stock.

    Args:
        code: 3- or 5-digit TSE stock code.
    Returns:
        {code, name, market, sector, market_cap_m, pe, pb, dividend_yield, prev_close, price}
    """
    code5 = code.zfill(5)
    val = _api_req("/equities/valuation", {"code": code5})
    rec = val.get("data", [{}])[0] if val.get("data") else {}
    master = _api_req("/equities/master", {"code": code5})
    mrec = master.get("data", [{}])[0] if master.get("data") else {}
    return {
        "code": code5,
        "name": mrec.get("CoName"),
        "name_en": mrec.get("CoNameEn"),
        "market": mrec.get("MktNm"),
        "sector_17": mrec.get("S17Nm"),
        "sector_33": mrec.get("S33Nm"),
        "market_cap_million_jpy": rec.get("MktCap"),
        "pe": rec.get("Per"),
        "pb": rec.get("Pbr"),
        "dividend_yield_pct": rec.get("DivYield"),
        "price": rec.get("C"),
        "prev_close": rec.get("PrevC"),
        "eps": rec.get("Eps"),
        "bps": rec.get("Bps"),
    }


@mcp.tool()
async def get_financial_summary(code: str, period: str = "latest") -> Dict[str, Any]:
    """Financial summary (Sales / OP / Net Income) — cumulative fiscal period.

    Args:
        code: 3- or 5-digit TSE stock code.
        period: "latest" (default) or a specific quarter like "1Q"/"2Q"/"3Q"/"FY".
    Returns:
        {code, name, periods: [{fiscal_period, sales, op, od_p, np, bps, eps}]}
    """
    code5 = code.zfill(5)
    fp = f"/fins/summary?code={code5}&fiscal_period={period}"
    fin = _api_req(fp, {})
    master = _api_req("/equities/master", {"code": code5})
    mrec = master.get("data", [{}])[0] if master.get("data") else {}
    rows = fin.get("data", [])
    out = []
    for r in rows:
        out.append({
            "fiscal_period": r.get("FiscalPeriod"),
            "sales_m": r.get("Sales"),
            "op_m": r.get("OP"),
            "odp_m": r.get("OdP"),
            "np_m": r.get("NP"),
            "bps": r.get("Bps"),
            "eps": r.get("Eps"),
        })
    return {
        "code": code5,
        "name": mrec.get("CoName"),
        "period_requested": period,
        "rows": out,
        "note": "Sales/OP/OdP/NP are cumulative (e.g. 3Q = 9-month total).",
    }


@mcp.tool()
async def get_calendar(year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
    """Trading calendar for JPX. Free plan: back to 2 years.

    Args:
        year: e.g. 2026. Defaults to current year.
        month: e.g. 10. Defaults to current month.
    Returns:
        {year, month, holidays: [date_str], trading_days_count}
    """
    y = year or date.today().year
    m = month or date.today().month
    params: Dict[str, str] = {"from": f"{y}-{m:02d}-01", "to": f"{y}-{m+1 if m<12 else m+1}-01"}
    cal = _api_req("/markets/calendar", params)
    holidays = [r.get("Date") for r in cal.get("data", [])]
    trading = [d for d in holidays if not d]  # trading days aren't in holiday list
    return {"year": y, "month": m, "holidays": holidays, "note": "J-Quants returns holiday dates only."}


@mcp.tool()
async def sector_list() -> Dict[str, Any]:
    """List all 33-sector and 17-sector classifications with codes.

    Returns:
        {sectors_33: {code: name}, sectors_17: {code: name}}
    """
    return {
        "sectors_33": SECTOR_33,
        "sectors_17": {str(i): f"Type {i}" for i in range(1, 18)},
        "note": "Use S33 code when filtering screener.sector field.",
        "sector_aliases": S33_SECTOR_FILTER,
    }


def _api_req(path: str, params: Dict[str, str] | None = None) -> Any:
    return _req(path, params)


if __name__ == "__main__":
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
