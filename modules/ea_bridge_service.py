import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from modules.quant_engine import evaluate_past_actuals_regime, has_valid_num
from modules.ai_analyzer import rule_based_sentiment_analysis

EA_HEARTBEAT_FILE = Path(__file__).resolve().parent.parent / "data" / "ea_heartbeat.json"


def _clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, float(val)))


def _detect_news_blackout(calendar_data: Dict[str, Any], now_ts: float) -> Dict[str, Any]:
    """
    Checks upcoming & recently passed High-Impact USD events so the 24h MT5 EA
    pauses new technical entries during [T-30m, T+15m] spread/whipsaw spikes.
    """
    candidates: List[Dict[str, Any]] = []
    next_ev = calendar_data.get("next_event")
    if isinstance(next_ev, dict) and not next_ev.get("is_waiting"):
        candidates.append(next_ev)
    for ev in (calendar_data.get("upcoming_events") or []):
        if isinstance(ev, dict):
            candidates.append(ev)
    for ev in (calendar_data.get("past_events") or [])[-3:]:
        if isinstance(ev, dict):
            candidates.append(ev)

    closest_minutes: Optional[int] = None
    closest_name = "NONE"
    blackout = False
    reason = "CLEAR"

    for ev in candidates:
        ev_ts = ev.get("timestamp")
        if not ev_ts and ev.get("datetime"):
            try:
                ev_ts = datetime.fromisoformat(str(ev["datetime"])).timestamp()
            except Exception:
                ev_ts = None
        if not ev_ts:
            continue

        diff_min = int(round((float(ev_ts) - now_ts) / 60.0))
        g_name = str(ev.get("group_name") or ev.get("title") or "USD News").replace("=", "").replace("\n", " ").strip()

        # Track closest future event (>= -15 min)
        if diff_min >= -15:
            if closest_minutes is None or abs(diff_min) < abs(closest_minutes):
                closest_minutes = diff_min
                closest_name = g_name

        # Blackout window: 30 min before to 15 min after release
        if -15 <= diff_min <= 30:
            blackout = True
            if diff_min >= 0:
                reason = f"PRE_NEWS_{g_name}_T-{diff_min}M"
            else:
                reason = f"POST_NEWS_{g_name}_T+{abs(diff_min)}M"
            closest_minutes = diff_min
            closest_name = g_name
            break

    return {
        "news_blackout": blackout,
        "blackout_reason": reason,
        "minutes_to_event": closest_minutes if closest_minutes is not None else 9999,
        "next_event_name": closest_name,
    }


def build_ea_macro_signal(
    calendar_data: Dict[str, Any],
    news_data: List[Dict[str, Any]],
    market_factors: Dict[str, Any],
    flash_alert: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds the 24/7 continuous institutional Macro & Intermarket regime feed for MT5 XAUUSD EA.
    Independent of the H-3 event waiting gate so hedge-fund technical + macro execution runs 24/5.
    """
    now_ts = time.time()
    mf = market_factors or {}

    # 1. Intermarket Quant Score [-1.0 .. +1.0] (Yields 40%, DXY 35%, Oil 15%, Stretch 10%)
    intermarket_score = float(mf.get("intermarket_score", 0.0) or 0.0)

    # 2. Preceding High-Impact Actuals Macro Regime (normalized from [-4.8, 4.8] -> [-1.0, 1.0])
    past_events = (calendar_data or {}).get("past_events") or []
    past_regime = evaluate_past_actuals_regime(past_events)
    past_regime_norm = _clamp(float(past_regime.get("regime_score", 0.0) or 0.0) / 4.8, -1.0, 1.0)

    # 3. Real-time Headline Macro & Geopolitical Sentiment (rule-based, zero LLM latency)
    headline_eval = rule_based_sentiment_analysis(news_data or [])
    geo_norm = _clamp(float(headline_eval.get("geo_score", 0.0) or 0.0) / 3.0, -1.0, 1.0)
    macro_hl_norm = _clamp(float(headline_eval.get("macro_score", 0.0) or 0.0) / 4.0, -1.0, 1.0)
    headline_norm = _clamp(macro_hl_norm * 0.65 + geo_norm * 0.35, -1.0, 1.0)

    # Composite Hedge-Fund Macro Score [-100 .. +100]
    composite = _clamp(
        (intermarket_score * 0.50) + (past_regime_norm * 0.30) + (headline_norm * 0.20),
        -1.0,
        1.0,
    )
    macro_score = int(round(composite * 100.0))

    if macro_score >= 20:
        macro_bias = "BULLISH"
    elif macro_score <= -20:
        macro_bias = "BEARISH"
    else:
        macro_bias = "NEUTRAL"

    # Volatility-Targeted Lot Multiplier (AQR / Bridgewater Volatility Parity principle)
    vol_regime = str(mf.get("volatility_regime", "NORMAL")).upper()
    vol_mult_map = {
        "LOW": 1.10,
        "NORMAL": 1.00,
        "HIGH": 0.75,
        "EXTREME": 0.50,
        "ELEVATED": 0.80,
    }
    vol_lot_mult = vol_mult_map.get(vol_regime, 0.85)

    # News Blackout Shield
    hazard = _detect_news_blackout(calendar_data or {}, now_ts)

    # Optional Flash Release Override (only when high-confidence post-release direction confirms)
    flash_bias = "NONE"
    flash_conf = 0
    if flash_alert and (now_ts - float(flash_alert.get("detected_at", 0) or 0)) <= 600:
        fsig = flash_alert.get("signal") or {}
        f_bias = str(fsig.get("expected_bias", "NEUTRAL")).upper()
        f_conf = int(fsig.get("context_percent", 0) or 0)
        f_mode = str(fsig.get("entry_mode", ""))
        if f_bias in ("BUY", "SELL") and f_conf >= 72 and "WAIT M5" not in f_mode:
            flash_bias = f_bias
            flash_conf = f_conf

    return {
        "status": "ok",
        "symbol": "XAUUSD",
        "server_ts": int(now_ts),
        "expires_in_sec": 300,
        "macro_bias": macro_bias,
        "macro_score": macro_score,
        "volatility_regime": vol_regime,
        "vol_lot_mult": round(vol_lot_mult, 2),
        "news_blackout": hazard["news_blackout"],
        "blackout_reason": hazard["blackout_reason"],
        "minutes_to_event": hazard["minutes_to_event"],
        "next_event_name": hazard["next_event_name"],
        "flash_bias": flash_bias,
        "flash_conf": flash_conf,
        "intermarket_score": round(intermarket_score, 3),
        "past_regime_score": round(float(past_regime.get("regime_score", 0.0) or 0.0), 2),
        "headline_score": round(headline_norm, 3),
        "dxy_price": float(mf.get("dxy_price", 0.0) or 0.0),
        "yield_10y": float(mf.get("yield_10y", 0.0) or 0.0),
        "xau_atr_h1_pips": int(mf.get("xau_atr_h1_pips", 160) or 160),
        "xau_stretch_z": float(mf.get("xau_stretch_z", 0.0) or 0.0),
        "counter_spike_risk": float(mf.get("counter_spike_risk", 0.35) or 0.35),
        "market_source": str(mf.get("source_status", "fallback")),
    }


def format_ea_kv(payload: Dict[str, Any]) -> str:
    """Formats signal dict as flat KEY=VALUE lines for bulletproof MQL5 WebRequest parsing."""
    lines = []
    for key, val in payload.items():
        if isinstance(val, bool):
            val_str = "1" if val else "0"
        else:
            val_str = str(val).replace("\n", " ").replace("\r", " ")
        lines.append(f"{key.upper()}={val_str}")
    return "\n".join(lines) + "\n"


def update_ea_heartbeat(data: Dict[str, Any]) -> Dict[str, Any]:
    """Stores latest telemetry reported by the running MT5 Demo EA."""
    EA_HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = dict(data)
    record["received_at"] = int(time.time())
    record["received_iso"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(EA_HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
    except Exception as e:
        print(f"[EA Bridge] Heartbeat write error: {e}")
    return record


def get_ea_heartbeat() -> Dict[str, Any]:
    """Returns latest stored EA heartbeat telemetry if available."""
    if EA_HEARTBEAT_FILE.exists():
        try:
            with open(EA_HEARTBEAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"status": "no_ea_connected"}

