import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "market_quant_cache.json"
CACHE_TTL_SECONDS = 300  # 5 minutes

TV_CFD_SCAN_URL = "https://scanner.tradingview.com/cfd/scan"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def _clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, float(val)))


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _fetch_tradingview_cfd() -> Dict[str, Dict[str, Optional[float]]]:
    """Fetch technical & volatility metrics for OANDA:XAUUSD and TVC:DXY from TradingView."""
    payload = {
        "symbols": {
            "tickers": ["OANDA:XAUUSD", "TVC:DXY"],
            "query": {"types": []}
        },
        "columns": ["close", "change", "ATR", "ATR|60", "RSI", "EMA20", "EMA50", "EMA200"]
    }
    req = urllib.request.Request(
        TV_CFD_SCAN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    out: Dict[str, Dict[str, Optional[float]]] = {}
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        for row in data.get("data", []):
            sym = row.get("s", "")
            vals = row.get("d", [])
            if len(vals) >= 8:
                out[sym] = {
                    "close": _safe_float(vals[0]),
                    "change_pct": _safe_float(vals[1]),
                    "atr_d1": _safe_float(vals[2]),
                    "atr_h1": _safe_float(vals[3]),
                    "rsi": _safe_float(vals[4]),
                    "ema20": _safe_float(vals[5]),
                    "ema50": _safe_float(vals[6]),
                    "ema200": _safe_float(vals[7]),
                }
    return out


def _fetch_yahoo_series(symbol: str) -> Dict[str, Any]:
    """Fetch 1-month daily closes for a Yahoo Finance symbol and compute 1d/5d changes."""
    encoded = urllib.parse.quote(symbol, safe="")
    url = YAHOO_CHART_URL.format(symbol=encoded)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    result = (data.get("chart", {}).get("result") or [{}])[0]
    meta = result.get("meta", {})
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    raw_closes = quote.get("close") or []
    closes: List[float] = [float(c) for c in raw_closes if c is not None]

    latest = _safe_float(meta.get("regularMarketPrice"))
    if latest is None and closes:
        latest = closes[-1]

    if not closes or latest is None:
        return {}

    prev_1d = closes[-2] if len(closes) >= 2 else closes[-1]
    prev_5d = closes[-6] if len(closes) >= 6 else closes[0]

    chg_1d_pct = ((latest - prev_1d) / prev_1d * 100.0) if prev_1d else 0.0
    chg_5d_pct = ((latest - prev_5d) / prev_5d * 100.0) if prev_5d else 0.0
    chg_5d_diff = latest - prev_5d

    # Compute 14-day ATR approximation if high/low available (backup if TV fails)
    highs = [h for h in (quote.get("high") or []) if h is not None]
    lows = [l for l in (quote.get("low") or []) if l is not None]
    atr_approx = None
    if len(highs) >= 10 and len(lows) >= 10:
        spans = [float(h) - float(l) for h, l in zip(highs[-14:], lows[-14:])]
        if spans:
            atr_approx = sum(spans) / len(spans)

    return {
        "price": round(latest, 4),
        "chg_1d_pct": round(chg_1d_pct, 2),
        "chg_5d_pct": round(chg_5d_pct, 2),
        "chg_5d_diff": round(chg_5d_diff, 4),
        "atr_d1_approx": round(atr_approx, 2) if atr_approx is not None else None,
        "ema20_approx": round(sum(closes[-20:]) / len(closes[-20:]), 2) if closes else None,
    }


def _default_offline_snapshot() -> Dict[str, Any]:
    """Safe neutral snapshot returned only when all network feeds fail."""
    return {
        "source_status": "fallback",
        "fetched_at": int(time.time()),
        "xau_price": 0.0,
        "xau_atr_d1": 85.0,
        "xau_atr_h1": 16.0,
        "xau_atr_h1_pips": 160,
        "spike_pips_low": 145,
        "spike_pips_high": 255,
        "spike_pips_label": "±145 - 255 pips",
        "xau_rsi": 50.0,
        "xau_stretch_z": 0.0,
        "dxy_price": 0.0,
        "dxy_rsi": 50.0,
        "dxy_chg_pct": 0.0,
        "dxy_trend_score": 0.0,
        "yield_10y": 0.0,
        "yield_5y": 0.0,
        "yield_10y_5d_pct": 0.0,
        "yield_5y_5d_pct": 0.0,
        "yield_pressure_score": 0.0,
        "oil_price": 0.0,
        "oil_5d_pct": 0.0,
        "oil_inflation_score": 0.0,
        "stretch_reversion_score": 0.0,
        "intermarket_score": 0.0,
        "intermarket_label": "NEUTRAL (OFFLINE FALLBACK)",
        "volatility_regime": "ELEVATED",
        "counter_spike_risk": 0.35,
    }


def compute_market_quant_metrics(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Compute normalized Z-scores, intermarket scores, and ATR pip estimates from raw market feeds."""
    tv_xau = raw.get("tv", {}).get("OANDA:XAUUSD") or {}
    tv_dxy = raw.get("tv", {}).get("TVC:DXY") or {}
    yh_tnx = raw.get("yahoo", {}).get("^TNX") or {}
    yh_fvx = raw.get("yahoo", {}).get("^FVX") or {}
    yh_oil = raw.get("yahoo", {}).get("CL=F") or {}
    yh_gcf = raw.get("yahoo", {}).get("GC=F") or {}
    yh_dxy = raw.get("yahoo", {}).get("DX-Y.NYB") or {}

    if not tv_xau and not yh_tnx and not yh_gcf:
        return _default_offline_snapshot()

    xau_price = _safe_float(tv_xau.get("close"), _safe_float(yh_gcf.get("price"), 0.0)) or 0.0
    xau_atr_d1 = _safe_float(tv_xau.get("atr_d1"), _safe_float(yh_gcf.get("atr_d1_approx"), 85.0)) or 85.0
    # Fallback H1 ATR ~ 18% of D1 ATR when TradingView H1 column is unavailable
    xau_atr_h1 = _safe_float(tv_xau.get("atr_h1"), round(xau_atr_d1 * 0.18, 2)) or 16.0
    xau_rsi = _safe_float(tv_xau.get("rsi"), 50.0) or 50.0
    xau_ema20 = _safe_float(tv_xau.get("ema20"), _safe_float(yh_gcf.get("ema20_approx")))
    xau_ema50 = _safe_float(tv_xau.get("ema50"))

    # XAU ATR pips (1 pip = $0.10)
    xau_atr_h1_pips = max(40, int(round(xau_atr_h1 * 10)))
    spike_pips_low = int(round(xau_atr_h1_pips * 0.90))
    spike_pips_high = int(round(xau_atr_h1_pips * 1.60))
    spike_pips_label = f"±{spike_pips_low} - {spike_pips_high} pips"

    # Technical Stretch Z-Score relative to EMA20 scaled by 0.5*D1_ATR
    xau_stretch_z = 0.0
    if xau_price > 0 and xau_ema20 and xau_atr_d1 > 0:
        scale = max(xau_atr_d1 * 0.50, 15.0)
        xau_stretch_z = _clamp((xau_price - xau_ema20) / scale, -3.0, 3.0)

    # Mean-reversion score (positive supports bounce when deeply oversold, negative warns pullback)
    stretch_reversion_score = 0.0
    if xau_rsi >= 70.0 or xau_stretch_z >= 1.6:
        stretch_reversion_score = _clamp(-((max(xau_rsi - 65.0, 0.0) / 20.0) * 0.5 + max(xau_stretch_z - 1.2, 0.0) * 0.35), -1.0, 0.0)
    elif xau_rsi <= 32.0 or xau_stretch_z <= -1.6:
        stretch_reversion_score = _clamp(((max(38.0 - xau_rsi, 0.0) / 20.0) * 0.5 + max(-1.2 - xau_stretch_z, 0.0) * 0.35), 0.0, 1.0)
    elif xau_stretch_z <= -0.8:
        stretch_reversion_score = 0.15
    elif xau_stretch_z >= 0.8:
        stretch_reversion_score = -0.15

    # DXY Trend -> XAU impact (-1.0 bearish XAU when DXY strong, +1.0 bullish XAU when DXY weak)
    dxy_price = _safe_float(tv_dxy.get("close"), _safe_float(yh_dxy.get("price"), 0.0)) or 0.0
    dxy_chg_pct = _safe_float(tv_dxy.get("change_pct"), _safe_float(yh_dxy.get("chg_1d_pct"), 0.0)) or 0.0
    dxy_rsi = _safe_float(tv_dxy.get("rsi"), 50.0) or 50.0
    dxy_ema20 = _safe_float(tv_dxy.get("ema20"), _safe_float(yh_dxy.get("ema20_approx")))
    dxy_ema50 = _safe_float(tv_dxy.get("ema50"))

    dxy_strength = 0.0
    if dxy_price > 0:
        if dxy_ema20 and dxy_price > dxy_ema20:
            dxy_strength += 0.30
        elif dxy_ema20 and dxy_price < dxy_ema20:
            dxy_strength -= 0.30
        if dxy_ema50 and dxy_price > dxy_ema50:
            dxy_strength += 0.25
        elif dxy_ema50 and dxy_price < dxy_ema50:
            dxy_strength -= 0.25
        dxy_strength += _clamp((dxy_rsi - 50.0) / 30.0, -0.35, 0.35)
        dxy_strength += _clamp(dxy_chg_pct / 1.2, -0.35, 0.35)
    # Invert because strong DXY is bearish XAU
    dxy_trend_score = _clamp(-dxy_strength, -1.0, 1.0)

    # US Treasury Yields 5-day surge -> rising yields are bearish XAU
    yield_10y = _safe_float(yh_tnx.get("price"), 0.0) or 0.0
    yield_5y = _safe_float(yh_fvx.get("price"), 0.0) or 0.0
    yield_10y_5d_pct = _safe_float(yh_tnx.get("chg_5d_pct"), 0.0) or 0.0
    yield_5y_5d_pct = _safe_float(yh_fvx.get("chg_5d_pct"), 0.0) or 0.0

    avg_yield_5d_pct = (yield_10y_5d_pct * 0.6 + yield_5y_5d_pct * 0.4)
    yield_pressure_score = _clamp(-avg_yield_5d_pct / 5.5, -1.0, 1.0)
    # Penalize elevated nominal 10Y level (> 4.75%) slightly
    if yield_10y >= 4.75:
        yield_pressure_score = _clamp(yield_pressure_score - 0.15, -1.0, 1.0)

    # WTI Crude Oil 5-day change -> surging oil = sticky headline inflation risk = bearish XAU via hawkish Fed
    oil_price = _safe_float(yh_oil.get("price"), 0.0) or 0.0
    oil_5d_pct = _safe_float(yh_oil.get("chg_5d_pct"), 0.0) or 0.0
    oil_inflation_score = _clamp(-oil_5d_pct / 8.0, -0.8, 0.8)

    # Combined Intermarket Quantitative Score [-1.0, +1.0] (XAU direction)
    intermarket_score = _clamp(
        (yield_pressure_score * 0.40) +
        (dxy_trend_score * 0.35) +
        (oil_inflation_score * 0.15) +
        (stretch_reversion_score * 0.10),
        -1.0,
        1.0
    )

    if intermarket_score >= 0.25:
        intermarket_label = "TAILWIND BULLISH XAU (Yields/DXY Lemah)"
    elif intermarket_score <= -0.25:
        intermarket_label = "HEADWIND BEARISH XAU (Yields/DXY Menguat)"
    else:
        intermarket_label = "MIXED / KONSOLIDASI INTERMARKET"

    # Volatility regime based on XAU ATR H1
    if xau_atr_h1 >= 22.0 or xau_atr_d1 >= 120.0:
        volatility_regime = "EXTREME"
    elif xau_atr_h1 >= 14.0 or xau_atr_d1 >= 80.0:
        volatility_regime = "HIGH"
    elif xau_atr_h1 >= 8.0:
        volatility_regime = "NORMAL"
    else:
        volatility_regime = "LOW"

    # Counter-spike / Stop-Hunt Hazard [0.0 .. 1.0]
    atr_risk = _clamp((xau_atr_h1 - 8.0) / 18.0, 0.10, 0.70)
    stretch_risk = _clamp(abs(xau_stretch_z) * 0.20, 0.0, 0.30)
    counter_spike_risk = round(_clamp(atr_risk + stretch_risk, 0.15, 0.98), 2)

    return {
        "source_status": "live",
        "fetched_at": int(time.time()),
        "xau_price": round(xau_price, 2),
        "xau_atr_d1": round(xau_atr_d1, 2),
        "xau_atr_h1": round(xau_atr_h1, 2),
        "xau_atr_h1_pips": xau_atr_h1_pips,
        "spike_pips_low": spike_pips_low,
        "spike_pips_high": spike_pips_high,
        "spike_pips_label": spike_pips_label,
        "xau_rsi": round(xau_rsi, 2),
        "xau_ema20": round(xau_ema20, 2) if xau_ema20 else None,
        "xau_ema50": round(xau_ema50, 2) if xau_ema50 else None,
        "xau_stretch_z": round(xau_stretch_z, 2),
        "dxy_price": round(dxy_price, 3),
        "dxy_rsi": round(dxy_rsi, 2),
        "dxy_chg_pct": round(dxy_chg_pct, 2),
        "dxy_trend_score": round(dxy_trend_score, 3),
        "yield_10y": round(yield_10y, 3),
        "yield_5y": round(yield_5y, 3),
        "yield_10y_5d_pct": round(yield_10y_5d_pct, 2),
        "yield_5y_5d_pct": round(yield_5y_5d_pct, 2),
        "yield_pressure_score": round(yield_pressure_score, 3),
        "oil_price": round(oil_price, 2),
        "oil_5d_pct": round(oil_5d_pct, 2),
        "oil_inflation_score": round(oil_inflation_score, 3),
        "stretch_reversion_score": round(stretch_reversion_score, 3),
        "intermarket_score": round(intermarket_score, 3),
        "intermarket_label": intermarket_label,
        "volatility_regime": volatility_regime,
        "counter_spike_risk": counter_spike_risk,
    }


def get_market_quant_factors(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns cached (5-min TTL) live quantitative market factors:
    OANDA:XAUUSD (ATR H1/D1, RSI, EMA stretch), TVC:DXY, US Yields (^TNX, ^FVX), WTI Oil (CL=F).
    """
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    now_ts = time.time()

    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if now_ts - float(cached.get("fetched_at", 0)) < CACHE_TTL_SECONDS:
                return cached
        except Exception:
            pass

    raw: Dict[str, Any] = {"tv": {}, "yahoo": {}}
    try:
        raw["tv"] = _fetch_tradingview_cfd()
    except Exception as e:
        print(f"[MarketQuant] TradingView fetch warning: {e}")

    for sym in ("^TNX", "^FVX", "CL=F"):
        try:
            raw["yahoo"][sym] = _fetch_yahoo_series(sym)
        except Exception as e:
            print(f"[MarketQuant] Yahoo {sym} warning: {e}")

    # Only pull Yahoo gold/DXY proxies if TradingView failed to return them
    if "OANDA:XAUUSD" not in raw["tv"]:
        try:
            raw["yahoo"]["GC=F"] = _fetch_yahoo_series("GC=F")
        except Exception:
            pass
    if "TVC:DXY" not in raw["tv"]:
        try:
            raw["yahoo"]["DX-Y.NYB"] = _fetch_yahoo_series("DX-Y.NYB")
        except Exception:
            pass

    metrics = compute_market_quant_metrics(raw)

    # Preserve last live snapshot if live fetch completely failed and stale cache exists
    if metrics.get("source_status") == "fallback" and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                stale = json.load(f)
            if stale.get("source_status") == "live":
                stale["source_status"] = "stale_cache"
                return stale
        except Exception:
            pass

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
    except Exception as e:
        print(f"[MarketQuant] Cache write error: {e}")

    return metrics

