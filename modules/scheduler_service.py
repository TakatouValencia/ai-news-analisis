import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Set
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news, get_daily_macro_bulletins
from modules.market_quant_service import get_market_quant_factors
from modules.ai_analyzer import analyze_with_llm
from modules.quant_engine import compute_full_quant_signal, has_valid_num
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
        self.last_bulletins: list = []
        self.latest_breaking_bulletin: Any = None
        self.last_market_factors: Dict[str, Any] = {}
        self.last_flash_alert: Dict[str, Any] = {}
        self._fast_poll_active: bool = False

    def perform_full_cycle(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Runs calendar fetch, live market quant factors, geopolitical intelligence, and quant signal calculation."""
        calendar_data = get_economic_calendar(force_refresh=force_refresh)
        self.last_calendar = calendar_data
        next_ev = calendar_data.get("next_event")
        
        news_data = get_latest_geopolitical_news(force_refresh=force_refresh)
        self.last_news = news_data

        market_factors = get_market_quant_factors(force_refresh=force_refresh)
        self.last_market_factors = market_factors
        
        daily_bulletins = get_daily_macro_bulletins(force_refresh=force_refresh)
        self.last_bulletins = daily_bulletins
        important = [b for b in daily_bulletins if b.get("is_important")]
        if important:
            self.latest_breaking_bulletin = important[0]
        
        group_name = next_ev.get("group_name", "WAITING NEWS") if next_ev else "WAITING NEWS"
        is_waiting = not next_ev or bool(next_ev.get("is_waiting")) or group_name == "WAITING NEWS"
        
        # Only run event-specific AI analysis when within the H-3 (3 days) active window
        now_ts = datetime.now(timezone.utc).timestamp()
        if is_waiting:
            ai_res = {
                "geo_score": 0.0,
                "macro_score": 0.0,
                "geopolitical_sentiment": "neutral",
                "summary_reasoning": "Status WAITING NEWS aktif: Tidak ada rilis NFP, PPI, CPI, FOMC, atau PMI dalam 3 hari ke depan. Analisa AI Quant keluar pada H-3.",
                "mode": "WAITING H-3"
            }
        elif not force_refresh and self.last_signal and (now_ts - getattr(self, "last_ai_time", 0) < 900) and getattr(self, "last_ai_group", "") == group_name:
            ai_res = getattr(self, "last_ai_res", {})
        else:
            ai_res = analyze_with_llm(news_data, group_name, market_factors=market_factors)
            self.last_ai_res = ai_res
            self.last_ai_time = now_ts
            self.last_ai_group = group_name
        
        signal = compute_full_quant_signal(
            next_ev,
            ai_res,
            past_events=calendar_data.get("past_events", []),
            market_factors=market_factors
        )
        self.last_signal = signal
        
        return {
            "calendar": calendar_data,
            "next_event": next_ev,
            "correlated_news": calendar_data.get("correlated_news", []),
            "news": news_data,
            "daily_bulletins": daily_bulletins,
            "latest_breaking_news": self.latest_breaking_bulletin,
            "market_factors": market_factors,
            "flash_release": self.last_flash_alert if (now_ts - self.last_flash_alert.get("detected_at", 0) < 900) else None,
            "signal": signal,
            "server_time": datetime.now(timezone.utc).isoformat()
        }

    def _check_flash_release(self, state: Dict[str, Any], webhook_url: str, sent_keys: Set[str]):
        """Detects newly released actual prints within 10 minutes post-release and dispatches Phase 2 Flash Alert."""
        now_ts = datetime.now(timezone.utc).timestamp()
        past_events = state.get("calendar", {}).get("past_events", [])
        recent_ev = None
        for ev in past_events:
            try:
                ev_ts = datetime.fromisoformat(ev["datetime"]).timestamp()
            except Exception:
                continue
            age = now_ts - ev_ts
            if 0 <= age <= 600:
                recent_ev = ev
                break

        if not recent_ev:
            return False

        self._fast_poll_active = True
        items = recent_ev.get("items", [])
        has_actual = any(
            str(it.get("actual", "")).strip() not in ("", "-", "Pending")
            and has_valid_num(str(it.get("actual", "")))
            for it in items
        )
        if not has_actual:
            return False

        ev_dt = recent_ev.get("datetime", "")
        group_name = recent_ev.get("group_name", "USD News")
        flash_key = f"{ev_dt}_{group_name}_flash"
        if flash_key in sent_keys:
            return False

        ai_res = getattr(self, "last_ai_res", None) or analyze_with_llm(
            state.get("news", []), group_name, market_factors=state.get("market_factors")
        )
        # Ensure past_events excludes recent_ev itself when evaluating baseline regime
        prior_events = [e for e in past_events if e.get("datetime") != ev_dt]
        recent_eval = dict(recent_ev)
        recent_eval["is_waiting"] = False
        recent_eval["seconds_until"] = 0
        flash_signal = compute_full_quant_signal(
            recent_eval,
            ai_res,
            past_events=prior_events,
            market_factors=state.get("market_factors")
        )
        self.last_flash_alert = {
            "event": recent_eval,
            "signal": flash_signal,
            "detected_at": int(now_ts)
        }
        if webhook_url:
            print(f"[Scheduler] Sending FLASH RELEASE alert for {group_name} ({recent_ev.get('datetime_wib')})")
            send_discord_webhook(webhook_url, flash_signal, recent_eval, stage="flash_release")
        mark_alert_as_sent(flash_key)
        return True

    def check_and_send_scheduled_alerts(self):
        """Checks T-30m, T-5m pre-news windows and T+0..10m Phase 2 Flash Post-Release actuals."""
        state = self.perform_full_cycle(force_refresh=self._fast_poll_active)
        settings = load_settings()
        webhook_url = settings.get("discord_webhook_url", "").strip()
        sent_keys = get_sent_alert_keys()

        self._fast_poll_active = False
        # Check Phase 2 Flash Post-Release first
        self._check_flash_release(state, webhook_url, sent_keys)

        next_ev = state.get("next_event")
        if not next_ev or next_ev.get("is_waiting") or next_ev.get("group_name") == "WAITING NEWS":
            return

        seconds = next_ev.get("seconds_until", -1)
        if 0 <= seconds <= 60:
            self._fast_poll_active = True

        if not webhook_url or seconds <= 0 or next_ev.get("is_past", True):
            return
            
        event_time_str = next_ev.get("datetime", "")
        group_name = next_ev.get("group_name", "USD News")
        
        # T-30m window: between 25m and 32m (1500s - 1920s)
        if 1500 <= seconds <= 1920:
            alert_key = f"{event_time_str}_{group_name}_pre30"
            if alert_key not in sent_keys:
                print(f"[Scheduler] Sending T-30m alert for {group_name} ({next_ev.get('datetime_wib')})")
                send_discord_webhook(webhook_url, state["signal"], next_ev, stage="pre_news")
                mark_alert_as_sent(alert_key)
                
        # T-5m window: between 1m and 6m (60s - 360s)
        elif 60 <= seconds <= 360:
            alert_key = f"{event_time_str}_{group_name}_imminent5"
            if alert_key not in sent_keys:
                print(f"[Scheduler] Sending T-5m alert for {group_name} ({next_ev.get('datetime_wib')})")
                send_discord_webhook(webhook_url, state["signal"], next_ev, stage="imminent")
                mark_alert_as_sent(alert_key)

    def check_and_update_web_breaking_news(self):
        """Scans for new important breaking news bulletins and updates state for web interface display only."""
        bulletins = get_daily_macro_bulletins(force_refresh=False)
        self.last_bulletins = bulletins
        important = [b for b in bulletins if b.get("is_important")]
        if important:
            self.latest_breaking_bulletin = important[0]

    async def run_loop(self):
        self.is_running = True
        print("[Scheduler] News Monitoring Scheduler started (Adaptive Fast-Poll enabled).")
        cycle_count = 0
        while self.is_running:
            try:
                self.check_and_send_scheduled_alerts()
                self.check_and_update_web_breaking_news()
                cycle_count += 1
                if cycle_count >= 2:
                    cycle_count = 0
                    self.perform_full_cycle(force_refresh=False)
            except Exception as e:
                print(f"[Scheduler] Error in monitoring cycle: {e}")
            # Fast-poll every 15s around news release (T-60s to T+10m), otherwise 60s
            await asyncio.sleep(15 if self._fast_poll_active else 60)

    def trigger_test_alert(self, stage: str = "pre_news") -> Dict[str, Any]:
        """Manually trigger Discord alert immediately with latest live data."""
        state = self.perform_full_cycle()
        settings = load_settings()
        webhook_url = settings.get("discord_webhook_url", "").strip()
        
        if not state.get("next_event"):
            return {
                "success": False,
                "error": "Tidak ada jadwal event berita ekonomi mendatang yang terdeteksi."
            }
            
        return send_discord_webhook(webhook_url, state["signal"], state["next_event"], stage=stage)

# Global singleton
scheduler = NewsMonitoringScheduler()
