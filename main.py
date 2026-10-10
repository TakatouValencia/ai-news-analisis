import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import load_settings, save_settings
from modules.scheduler_service import scheduler
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news, get_daily_macro_bulletins
from modules.ai_analyzer import analyze_with_llm, interpret_single_news_item
from modules.quant_engine import compute_full_quant_signal

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
    if force or not scheduler.last_signal:
        state = scheduler.perform_full_cycle(force_refresh=force)
    else:
        # Use scheduler's in-memory calendar or cached calendar
        cal = scheduler.last_calendar if scheduler.last_calendar else get_economic_calendar(force_refresh=False)
        next_ev = cal.get("next_event")
        
        # Keep countdown seconds fresh in real time
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if next_ev and "timestamp" in next_ev:
            diff = next_ev["timestamp"] - now_ts
            next_ev["seconds_until"] = diff
            next_ev["is_past"] = diff < 0
            
        state = {
            "calendar": cal,
            "next_event": next_ev,
            "correlated_news": cal.get("correlated_news", []),
            "news": scheduler.last_news,
            "daily_bulletins": get_daily_macro_bulletins(),
            "signal": scheduler.last_signal,
            "server_time": datetime.now(timezone.utc).isoformat()
        }
    return JSONResponse(content=state)

@app.get("/api/daily-news")
async def get_daily_news_api():
    """Returns curated institutional daily news bulletins with full market interpretations."""
    bulletins = get_daily_macro_bulletins()
    return JSONResponse(content={"status": "success", "bulletins": bulletins})

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
        "ai_model": s.get("ai_model", "gemini-3.8-flash")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
