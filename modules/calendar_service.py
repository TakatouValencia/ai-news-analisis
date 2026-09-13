import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dateutil import parser as date_parser

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "calendar_cache.json"

THIS_WEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEXT_WEEK_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"

TARGET_KEYWORDS = [
    "cpi", "ppi", "fomc", "fed", "interest rate", "nfp", "non-farm",
    "unemployment", "jobless claims", "retail sales", "gdp", "ism"
]

def is_high_impact_event(event: Dict[str, Any]) -> bool:
    if event.get("country") != "USD":
        return False
    
    impact = event.get("impact", "").lower()
    title = event.get("title", "").lower()
    
    # Red folder / High impact
    if impact == "high":
        return True
        
    # High interest news even if classified as medium by some feeds
    if any(kw in title for kw in ["cpi", "ppi", "fomc", "fed", "non-farm", "jobless claims"]):
        if impact in ["high", "medium"]:
            return True
            
    return False

def fetch_raw_events() -> List[Dict[str, Any]]:
    events = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for url in [THIS_WEEK_URL, NEXT_WEEK_URL]:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    events.extend(data)
        except Exception as e:
            print(f"[CalendarService] Error fetching from {url}: {e}")
            
    return events

def get_simulated_fallback_events() -> List[Dict[str, Any]]:
    """Provides realistic fallback/upcoming events if live feeds are unreachable or weekend."""
    now = datetime.now(timezone.utc)
    # Schedule simulated high-impact events for demonstration / offline use
    e1_time = now + timedelta(minutes=42)
    e2_time = now + timedelta(hours=24)
    e3_time = now + timedelta(days=2, hours=4)
    
    return [
        {
            "title": "PPI m/m",
            "country": "USD",
            "date": e1_time.isoformat(),
            "impact": "High",
            "forecast": "-0.3%",
            "previous": "0.0%",
            "actual": ""
        },
        {
            "title": "Initial Jobless Claims",
            "country": "USD",
            "date": e1_time.isoformat(),
            "impact": "High",
            "forecast": "211K",
            "previous": "206K",
            "actual": ""
        },
        {
            "title": "CPI m/m",
            "country": "USD",
            "date": e2_time.isoformat(),
            "impact": "High",
            "forecast": "0.2%",
            "previous": "0.2%",
            "actual": ""
        },
        {
            "title": "Core CPI m/m",
            "country": "USD",
            "date": e2_time.isoformat(),
            "impact": "High",
            "forecast": "0.3%",
            "previous": "0.3%",
            "actual": ""
        },
        {
            "title": "FOMC Statement & Federal Funds Rate",
            "country": "USD",
            "date": e3_time.isoformat(),
            "impact": "High",
            "forecast": "5.25%",
            "previous": "5.50%",
            "actual": ""
        }
    ]

def group_events_by_time(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups events happening at the same datetime (e.g. PPI + Jobless Claims)."""
    grouped: Dict[str, Dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    
    for ev in events:
        try:
            ev_time = date_parser.parse(ev["date"])
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
        except Exception:
            continue
            
        time_key = ev_time.isoformat()
        
        if time_key not in grouped:
            # Determine main title
            main_title = ev.get("title", "USD News")
            # Simplify group title
            lower_title = main_title.lower()
            if "ppi" in lower_title:
                group_name = "PPI"
            elif "cpi" in lower_title:
                group_name = "CPI"
            elif "fomc" in lower_title or "federal funds" in lower_title:
                group_name = "FOMC"
            elif "non-farm" in lower_title or "nfp" in lower_title:
                group_name = "NFP"
            elif "jobless" in lower_title:
                group_name = "Initial Jobless Claims"
            else:
                group_name = main_title
                
            grouped[time_key] = {
                "group_name": group_name,
                "datetime": time_key,
                "timestamp": int(ev_time.timestamp()),
                "is_past": ev_time < now,
                "seconds_until": int((ev_time - now).total_seconds()),
                "items": []
            }
            
        grouped[time_key]["items"].append({
            "title": ev.get("title"),
            "impact": ev.get("impact"),
            "forecast": ev.get("forecast", "-"),
            "previous": ev.get("previous", "-"),
            "actual": ev.get("actual", "")
        })
        
    result = list(grouped.values())
    result.sort(key=lambda x: x["timestamp"])
    return result

def get_economic_calendar(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns parsed economic calendar and the next high-impact USD news cluster."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    raw_events = []
    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cache_time = cached.get("cached_at", 0)
                # Cache valid for 30 minutes
                if datetime.now(timezone.utc).timestamp() - cache_time < 1800:
                    raw_events = cached.get("raw_events", [])
        except Exception as e:
            print(f"[CalendarService] Cache read error: {e}")
            
    if not raw_events:
        fetched = fetch_raw_events()
        high_impact = [e for e in fetched if is_high_impact_event(e)]
        if high_impact:
            raw_events = high_impact
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "cached_at": int(datetime.now(timezone.utc).timestamp()),
                        "raw_events": raw_events
                    }, f, indent=2)
            except Exception as e:
                print(f"[CalendarService] Cache write error: {e}")
        else:
            # Fallback if weekend or API empty
            raw_events = get_simulated_fallback_events()
            
    grouped = group_events_by_time(raw_events)
    now = datetime.now(timezone.utc)
    
    # Recalculate seconds_until and status
    upcoming_clusters = []
    past_clusters = []
    
    # If no upcoming live events (e.g. end of week or past events only), append simulated upcoming events
    has_upcoming = any(g["timestamp"] > now.timestamp() for g in grouped)
    if not has_upcoming:
        fallback = get_simulated_fallback_events()
        grouped = group_events_by_time(fallback)
    
    for g in grouped:
        ev_dt = datetime.fromtimestamp(g["timestamp"], tz=timezone.utc)
        diff_sec = int((ev_dt - now).total_seconds())
        g["seconds_until"] = diff_sec
        g["is_past"] = diff_sec < 0
        
        # Countdown formatted string: "41m 57s" or "2h 15m" or "3d 4h"
        if diff_sec > 0:
            days = diff_sec // 86400
            hours = (diff_sec % 86400) // 3600
            minutes = (diff_sec % 3600) // 60
            seconds = diff_sec % 60
            
            if days > 0:
                g["countdown_str"] = f"{days}d {hours}h"
            elif hours > 0:
                g["countdown_str"] = f"{hours}h {minutes}m {seconds}s"
            else:
                g["countdown_str"] = f"{minutes}m {seconds}s"
            upcoming_clusters.append(g)
        else:
            g["countdown_str"] = "Released"
            past_clusters.append(g)
            
    next_event = upcoming_clusters[0] if upcoming_clusters else None
    
    return {
        "next_event": next_event,
        "upcoming_events": upcoming_clusters[:10],
        "past_events": past_clusters[-5:],
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
