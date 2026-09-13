import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import load_settings, save_settings
from modules.scheduler_service import scheduler
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news
from modules.ai_analyzer import analyze_with_llm
from modules.quant_engine import compute_full_quant_signal
from modules.discord_webhook import send_discord_webhook

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

app = FastAPI(title="EANews Analisis AI", lifespan=lifespan)

# Mount static directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class SettingsPayload(BaseModel):
    discord_webhook_url: str = ""
    ai_api_key: str = ""
    ai_base_url: str = "https://openrouter.ai/api/v1"
    ai_model: str = "google/gemini-2.5-flash"

class TriggerDiscordPayload(BaseModel):
    stage: str = "pre_news"

@app.get("/")
async def serve_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_file))

@app.get("/api/state")
async def get_state(force: bool = False):
    """Returns current state of calendar, next event, AI quant signal, and news."""
    if force or not scheduler.last_signal:
        state = scheduler.perform_full_cycle(force_refresh=force)
    else:
        # Re-fetch calendar to keep countdown seconds fresh
        cal = get_economic_calendar()
        scheduler.last_calendar = cal
        next_ev = cal.get("next_event")
        state = {
            "calendar": cal,
            "next_event": next_ev,
            "news": scheduler.last_news,
            "signal": scheduler.last_signal
        }
    return JSONResponse(content=state)

@app.post("/api/refresh")
async def refresh_data():
    """Forces fresh data fetch from feeds and AI recalculation."""
    state = scheduler.perform_full_cycle(force_refresh=True)
    return JSONResponse(content={"status": "success", "data": state})

@app.post("/api/trigger-discord")
async def trigger_discord(payload: TriggerDiscordPayload):
    """Manually test sends a formatted signal to Discord Webhook."""
    res = scheduler.trigger_test_alert(stage=payload.stage)
    return JSONResponse(content=res)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
