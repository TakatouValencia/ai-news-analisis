import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Set
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news
from modules.ai_analyzer import analyze_with_llm
from modules.quant_engine import compute_full_quant_signal
from modules.discord_webhook import send_discord_webhook
from config import load_settings

SENT_ALERTS_FILE = Path(__file__).resolve().parent.parent / "data" / "sent_alerts.json"

def get_sent_alert_keys() -> Set[str]:
    SENT_ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SENT_ALERTS_FILE.exists():
        try:
            with open(SENT_ALERTS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def mark_alert_as_sent(key: str):
    keys = get_sent_alert_keys()
    keys.add(key)
    try:
        with open(SENT_ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(keys), f)
    except Exception as e:
        print(f"[Scheduler] Error saving sent alert key: {e}")

class NewsMonitoringScheduler:
    def __init__(self):
        self.is_running = False
        self.last_signal: Dict[str, Any] = {}
        self.last_calendar: Dict[str, Any] = {}
        self.last_news: list = []

    def perform_full_cycle(self) -> Dict[str, Any]:
        """Runs calendar fetch, geopolitical intelligence, quant calculation, and returns full state."""
        calendar_data = get_economic_calendar()
        self.last_calendar = calendar_data
        next_ev = calendar_data.get("next_event")
        
        news_data = get_latest_geopolitical_news()
        self.last_news = news_data
        
        group_name = next_ev.get("group_name", "USD News") if next_ev else "USD News"
        ai_res = analyze_with_llm(news_data, group_name)
        
        signal = compute_full_quant_signal(next_ev, ai_res)
        self.last_signal = signal
        
        return {
            "calendar": calendar_data,
            "next_event": next_ev,
            "news": news_data,
            "signal": signal
        }

    def check_and_send_scheduled_alerts(self):
        """Checks if next event is within T-30m or T-5m, and sends Discord webhook if not yet sent."""
        state = self.perform_full_cycle()
        next_ev = state.get("next_event")
        if not next_ev:
            return
            
        settings = load_settings()
        webhook_url = settings.get("discord_webhook_url", "").strip()
        if not webhook_url:
            return
            
        seconds = next_ev.get("seconds_until", 99999)
        event_time_str = next_ev.get("datetime", "")
        sent_keys = get_sent_alert_keys()
        
        # T-30m window: between 25m and 32m (1500s - 1920s)
        if 1500 <= seconds <= 1920:
            alert_key = f"{event_time_str}_pre30"
            if alert_key not in sent_keys:
                print(f"[Scheduler] Sending T-30m alert for {next_ev.get('group_name')}")
                send_discord_webhook(webhook_url, state["signal"], next_ev, stage="pre_news")
                mark_alert_as_sent(alert_key)
                
        # T-5m window: between 1m and 6m (60s - 360s)
        elif 60 <= seconds <= 360:
            alert_key = f"{event_time_str}_imminent5"
            if alert_key not in sent_keys:
                print(f"[Scheduler] Sending T-5m alert for {next_ev.get('group_name')}")
                send_discord_webhook(webhook_url, state["signal"], next_ev, stage="imminent")
                mark_alert_as_sent(alert_key)

    async def run_loop(self):
        self.is_running = True
        print("[Scheduler] News Monitoring Scheduler started.")
        while self.is_running:
            try:
                self.check_and_send_scheduled_alerts()
            except Exception as e:
                print(f"[Scheduler] Error in monitoring cycle: {e}")
            # Check every 60 seconds
            await asyncio.sleep(60)

    def trigger_test_alert(self, stage: str = "pre_news") -> Dict[str, Any]:
        """Manually trigger Discord alert immediately with latest live data."""
        state = self.perform_full_cycle()
        settings = load_settings()
        webhook_url = settings.get("discord_webhook_url", "").strip()
        
        return send_discord_webhook(webhook_url, state["signal"], state["next_event"], stage=stage)

# Global singleton
scheduler = NewsMonitoringScheduler()
