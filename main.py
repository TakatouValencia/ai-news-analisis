import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import load_settings, save_settings
from modules.scheduler_service import scheduler
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news, get_daily_macro_bulletins
from modules.market_quant_service import get_market_quant_factors
from modules.ai_analyzer import analyze_with_llm, interpret_single_news_item
from modules.quant_engine import compute_full_quant_signal
from modules.ea_bridge_service import build_ea_macro_signal, format_ea_kv, update_ea_heartbeat, get_ea_heartbeat

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
STATIC_DIR = WEB_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run initial cycle and launch background task
    print("[Main] Starting EANews Analisis server...")
    scheduler.perform_full_cycle()
    task = asyncio.create_task(scheduler.run_loop())
    yield
    # Shutdown
    scheduler.is_running = False
    task.cancel()
    print("[Main] EANews Analisis server stopped.")

app = FastAPI(title="EANews Novaire AI", lifespan=lifespan)

@app.middleware("http")
async def add_cache_control_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount static directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class SettingsPayload(BaseModel):
    discord_webhook_url: str = ""
    ai_api_key: str = ""
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    ai_model: str = "gemini-3.8-flash"

@app.get("/")
async def serve_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    response = FileResponse(str(index_file))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/state")
async def get_state(force: bool = False):
    """Returns current state of calendar, next event, AI quant signal, and news."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    cached_next = scheduler.last_calendar.get("next_event") if scheduler.last_calendar else None
    event_expired = bool(cached_next and cached_next.get("timestamp", 0) > 0 and cached_next.get("timestamp", 0) <= now_ts)

    if force or not scheduler.last_signal or event_expired:
        state = scheduler.perform_full_cycle(force_refresh=force)
    else:
        cal = get_economic_calendar(force_refresh=False)
        next_ev = cal.get("next_event")
        group_changed = (next_ev or {}).get("group_name") != (cached_next or {}).get("group_name")
        if group_changed:
            state = scheduler.perform_full_cycle(force_refresh=False)
        else:
            scheduler.last_calendar = cal
            state = {
                "calendar": cal,
                "next_event": next_ev,
                "correlated_news": cal.get("correlated_news", []),
                "news": scheduler.last_news,
                "daily_bulletins": scheduler.last_bulletins if scheduler.last_bulletins else get_daily_macro_bulletins(),
                "latest_breaking_news": getattr(scheduler, "latest_breaking_bulletin", None),
                "signal": scheduler.last_signal,
                "server_time": datetime.now(timezone.utc).isoformat()
            }
    return JSONResponse(content=state)

@app.get("/api/daily-news")
async def get_daily_news_api(force: bool = False):
    """Returns curated institutional daily news bulletins with full market interpretations."""
    bulletins = get_daily_macro_bulletins(force_refresh=force)
    return JSONResponse(content={"status": "success", "bulletins": bulletins, "count": len(bulletins)})

@app.post("/api/daily-news/refresh")
async def refresh_daily_news_api():
    """Forces immediate live fetch and AI interpretation generation for daily bulletins."""
    bulletins = get_daily_macro_bulletins(force_refresh=True)
    scheduler.last_bulletins = bulletins
    important = [b for b in bulletins if b.get("is_important")]
    if important:
        scheduler.latest_breaking_bulletin = important[0]
    return JSONResponse(content={"status": "success", "bulletins": bulletins, "message": "Berita harian & interpretasi berhasil diperbarui!"})

class CustomInterpretPayload(BaseModel):
    text: str = ""

@app.post("/api/interpret-custom")
async def interpret_custom_news_api(payload: CustomInterpretPayload):
    """Interprets arbitrary user-pasted news text for XAU/USD impact and transmission."""
    cleaned_text = payload.text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="Teks berita tidak boleh kosong.")
    result = interpret_single_news_item(cleaned_text)
    return JSONResponse(content={"status": "success", "interpretation": result})

@app.post("/api/refresh")
async def refresh_data():
    """Forces fresh data fetch from feeds and AI recalculation."""
    state = scheduler.perform_full_cycle(force_refresh=True)
    return JSONResponse(content={"status": "success", "data": state})

@app.get("/api/settings")
async def get_settings():
    """Returns current settings (masking secret keys for safety)."""
    s = load_settings()
    # Mask API key partially for security
    raw_key = s.get("ai_api_key", "")
    masked_key = (raw_key[:6] + "..." + raw_key[-4:]) if len(raw_key) > 10 else raw_key
    return JSONResponse(content={
        "discord_webhook_url": s.get("discord_webhook_url", ""),
        "ai_api_key_masked": masked_key,
        "ai_base_url": s.get("ai_base_url", "https://generativelanguage.googleapis.com/v1beta/openai"),
        "ai_model": s.get("ai_model", "gemini-3.1-flash-lite")
    })

@app.post("/api/settings")
async def update_settings(payload: SettingsPayload):
    """Updates settings and persists to settings.json and .env."""
    to_update = {
        "discord_webhook_url": payload.discord_webhook_url.strip(),
        "ai_base_url": payload.ai_base_url.strip(),
        "ai_model": payload.ai_model.strip()
    }
    if payload.ai_api_key.strip():
        to_update["ai_api_key"] = payload.ai_api_key.strip()
    saved = save_settings(to_update)
    return JSONResponse(content={"status": "success", "message": "Pengaturan berhasil disimpan!"})


class EAHeartbeatPayload(BaseModel):
    account_mode: str = "DEMO"
    symbol: str = "XAUUSD"
    balance: float = 0.0
    equity: float = 0.0
    daily_pnl_pct: float = 0.0
    open_positions: int = 0
    spread_points: int = 0
    last_action: str = "IDLE"
    confluence_score: int = 0
    broker_server: str = ""


def _verify_ea_auth(api_key: str, x_ea_key: str) -> None:
    expected = str(load_settings().get("ea_api_key", "novaire-demo-2026")).strip()
    provided = (x_ea_key or api_key or "").strip()
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="Invalid EA API Key")


@app.get("/api/ea/signal")
async def get_ea_signal_api(
    format: str = "json",
    api_key: str = "",
    x_ea_key: str = Header(default=""),
):
    """24/7 Institutional Macro & Volatility signal bridge for MT5 XAUUSD Expert Advisor."""
    _verify_ea_auth(api_key, x_ea_key)
    cal = scheduler.last_calendar if scheduler.last_calendar else get_economic_calendar(force_refresh=False)
    news = scheduler.last_news if scheduler.last_news else get_latest_geopolitical_news(force_refresh=False)
    mf = get_market_quant_factors(force_refresh=False)
    flash = getattr(scheduler, "last_flash_alert", None)

    sig = build_ea_macro_signal(cal, news, mf, flash_alert=flash)
    if format.lower() == "kv":
        return PlainTextResponse(content=format_ea_kv(sig))
    return JSONResponse(content=sig)


@app.post("/api/ea/heartbeat")
async def post_ea_heartbeat_api(
    payload: EAHeartbeatPayload,
    api_key: str = "",
    x_ea_key: str = Header(default=""),
):
    """Receives live telemetry from the running MT5 Demo EA."""
    _verify_ea_auth(api_key, x_ea_key)
    saved = update_ea_heartbeat(payload.model_dump())
    return JSONResponse(content={"status": "ok", "telemetry": saved})


@app.get("/api/ea/status")
async def get_ea_status_api():
    """Returns last known MT5 EA heartbeat status."""
    return JSONResponse(content=get_ea_heartbeat())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
