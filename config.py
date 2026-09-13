import os
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
SETTINGS_FILE = BASE_DIR / "settings.json"

# Load initial environment
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)

DEFAULT_SETTINGS = {
    "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
    "ai_api_key": os.getenv("AI_API_KEY", "sk-CaegB3fmH2kAIhu1GfVWIklal9PcFu5NLCU8eY0dv0ufkLXt"),
    "ai_base_url": os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1"),
    "ai_model": os.getenv("AI_MODEL", "google/gemini-2.5-flash"),
    "server_port": int(os.getenv("SERVER_PORT", 8000)),
    "refresh_interval_minutes": int(os.getenv("REFRESH_INTERVAL_MINUTES", 5)),
    "auto_alert_pre_news_minutes": [30, 5],
    "high_impact_only": True,
    "target_currencies": ["USD"],
    "target_events": ["FOMC", "Fed Interest Rate", "CPI", "PPI", "Non-Farm Employment", "NFP", "Unemployment Rate", "Jobless Claims"]
}

def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"[Config] Warning loading settings.json: {e}")
            
    # Env overrides if explicitly defined
    env_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if env_webhook:
        settings["discord_webhook_url"] = env_webhook
        
    env_api_key = os.getenv("AI_API_KEY")
    if env_api_key:
        settings["ai_api_key"] = env_api_key
        
    return settings

def save_settings(new_settings: dict) -> dict:
    current = load_settings()
    current.update(new_settings)
    
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
        
    # Also update .env for persistence
    if "discord_webhook_url" in new_settings:
        set_key(str(ENV_FILE), "DISCORD_WEBHOOK_URL", str(new_settings["discord_webhook_url"]))
    if "ai_api_key" in new_settings:
        set_key(str(ENV_FILE), "AI_API_KEY", str(new_settings["ai_api_key"]))
    if "ai_base_url" in new_settings:
        set_key(str(ENV_FILE), "AI_BASE_URL", str(new_settings["ai_base_url"]))
    if "ai_model" in new_settings:
        set_key(str(ENV_FILE), "AI_MODEL", str(new_settings["ai_model"]))
        
    return current
