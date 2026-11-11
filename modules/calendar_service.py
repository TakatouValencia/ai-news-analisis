import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dateutil import parser as date_parser

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "calendar_cache.json"

FF_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TRADINGVIEW_CALENDAR_URL = "https://economic-calendar.tradingview.com/events"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/xml, */*"
}

TV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/"
}

def parse_utc_datetime(iso_str: str) -> datetime:
    """Safely parses any ISO datetime string and converts it to UTC timezone."""
    dt = date_parser.parse(iso_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def format_wib_datetime(iso_str: str) -> str:
    """Formats ISO datetime string to Indonesian WIB (GMT+7) human-readable format."""
    days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    try:
        dt = parse_utc_datetime(iso_str)
        wib = dt.astimezone(timezone(timedelta(hours=7)))
        day_name = days[wib.weekday()]
        month_name = months[wib.month - 1]
        return f"{day_name}, {wib.day:02d} {month_name} {wib.year} | {wib.strftime('%H:%M')} WIB"
    except Exception:
        return iso_str

def is_speech_or_testimony(title_lower: str) -> bool:
    """Checks if an event title is a central bank official speech or testimony rather than a data release."""
    return any(w in title_lower for w in ["speaks", "testifies", "speech", "remarks", "panel"])

ALLOWED_GROUPS = {"NFP", "PPI", "CPI", "FOMC", "PMI"}
H3_WINDOW_SECONDS = 3 * 86400  # 3 days (72 hours = 259,200 seconds)

def classify_event_group(title: str) -> str:
    """
    Strictly maps a raw USD economic indicator title to one of the 5 allowed High Impact groups:
    NFP, PPI, CPI, FOMC, PMI (plus NFP_COMPONENT for same-timestamp NFP companion metrics).
    Returns empty string "" for any other news event so it is excluded.
    """
    t = title.strip().lower()

    # 1. Exclude all individual speeches, testimonies, and FOMC Meeting Minutes
    if is_speech_or_testimony(t):
        return ""
    if "minutes" in t:
        return ""

    # 2. Official FOMC Rate Decision Cluster ONLY
    if any(
        w in t
        for w in [
            "federal funds rate",
            "fomc statement",
            "fomc economic projections",
            "fomc press conference",
            "fed interest rate",
            "interest rate decision"
        ]
    ) or t == "interest rate":
        return "FOMC"

    # 3. Official BLS Non-Farm Payrolls (NFP) & Same-Timestamp Companion Metrics
    if "adp" in t:
        return ""
    if (
        ("non-farm" in t or "non farm" in t or "nfp" in t or "jobs report" in t or "payrolls" in t)
        and "adp" not in t
        and "productivity" not in t
        and "weekly" not in t
    ):
        return "NFP"
    if "unemployment rate" in t or "average hourly earnings" in t:
        return "NFP_COMPONENT"

    # 4. Consumer Price Index (CPI)
    if (
        ("cpi" in t or "inflation rate" in t)
        and "expectation" not in t
        and "cpi-w" not in t
        and "nsa" not in t
    ):
        return "CPI"

    # 5. Producer Price Index (PPI)
    if "ppi" in t or "producer price" in t:
        return "PPI"

    # 6. Purchasing Managers' Index (PMI - ISM & Flash/S&P Global US PMI)
    if "pmi" in t and "chicago" not in t:
        return "PMI"
    if ("ism manufacturing" in t or "ism services" in t or "ism non-manufacturing" in t) and "prices" not in t and "employment" not in t:
        return "PMI"

    return ""

def is_high_impact_event(event: Dict[str, Any]) -> bool:
    """Strictly filters for ONLY the 5 High Impact USD groups: NFP, PPI, CPI, FOMC, PMI."""
    if event.get("country") != "USD":
        return False

    impact = str(event.get("impact", "")).strip().lower()
    title = str(event.get("title", "")).strip()

    if impact not in ["high", "medium"]:
        return False

    group = classify_event_group(title)
    return group in ALLOWED_GROUPS or group == "NFP_COMPONENT"

def fetch_from_forexfactory_xml() -> List[Dict[str, Any]]:
    req = urllib.request.Request(FF_XML_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as resp:
        root = ET.fromstring(resp.read())
    events = []
    for ev in root.findall("event"):
        country = ev.findtext("country", "")
        if country != "USD":
            continue
        title = (ev.findtext("title", "") or "").strip()
        d_str = (ev.findtext("date", "") or "").strip()
        t_str = (ev.findtext("time", "") or "").strip()
        impact = (ev.findtext("impact", "") or "").strip()
        forecast = (ev.findtext("forecast", "") or "").strip() or "-"
        previous = (ev.findtext("previous", "") or "").strip() or "-"
        actual = (ev.findtext("actual", "") or "").strip()

        if not title or not d_str or not t_str:
            continue

        try:
            dt = datetime.strptime(f"{d_str} {t_str}", "%m-%d-%Y %I:%M%p").replace(tzinfo=timezone.utc)
            iso_date = dt.isoformat()
        except Exception:
            continue

        events.append({
            "title": title,
            "country": "USD",
            "date": iso_date,
            "impact": impact,
            "forecast": forecast,
            "previous": previous,
            "actual": actual
        })
    return events

def fetch_from_forexfactory_json() -> List[Dict[str, Any]]:
    req = urllib.request.Request(FF_JSON_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, list):
            return []

    events = []
    for ev in data:
        if ev.get("country") != "USD":
            continue
        title = (ev.get("title") or "").strip()
        date_raw = (ev.get("date") or "").strip()
        if not title or not date_raw:
            continue
        try:
            dt = parse_utc_datetime(date_raw).replace(second=0, microsecond=0)
            iso_date = dt.isoformat()
        except Exception:
            continue

        events.append({
            "title": title,
            "country": "USD",
            "date": iso_date,
            "impact": (ev.get("impact") or "").strip(),
            "forecast": (str(ev.get("forecast") or "")).strip() or "-",
            "previous": (str(ev.get("previous") or "")).strip() or "-",
            "actual": (str(ev.get("actual") or "")).strip()
        })
    return events

def _format_tv_figure(val: Any, unit: Optional[str], scale: Optional[str]) -> str:
    if val is None or val == "":
        return "-"
    try:
        num = float(val)
        if num == int(num) and (scale in ["K", "M", "B"] or unit != "%"):
            num_str = str(int(num))
        else:
            num_str = f"{num:g}"
    except Exception:
        num_str = str(val).strip()

    s = scale or ""
    u = unit if unit == "%" else ""
    return f"{num_str}{s}{u}"

def _map_tradingview_title(raw_title: str) -> Optional[str]:
    """Maps TradingView economic calendar indicator names strictly to the 5 allowed USD groups (NFP, PPI, CPI, FOMC, PMI)."""
    t = raw_title.strip()
    tl = t.lower()

    mapping = {
        "core inflation rate mom": "Core CPI m/m",
        "core inflation rate yoy": "Core CPI y/y",
        "inflation rate mom": "CPI m/m",
        "inflation rate yoy": "CPI y/y",
        "ppi mom": "PPI m/m",
        "ppi yoy": "PPI y/y",
        "core ppi mom": "Core PPI m/m",
        "core ppi yoy": "Core PPI y/y",
        "non farm payrolls": "Non-Farm Employment Change",
        "unemployment rate": "Unemployment Rate",
        "average hourly earnings mom": "Average Hourly Earnings m/m",
        "average hourly earnings yoy": "Average Hourly Earnings y/y",
        "ism manufacturing pmi": "ISM Manufacturing PMI",
        "ism services pmi": "ISM Services PMI",
        "ism non-manufacturing pmi": "ISM Services PMI",
        "s&p global manufacturing pmi flash": "Flash Manufacturing PMI",
        "s&p global services pmi flash": "Flash Services PMI",
        "s&p global manufacturing pmi": "S&P Global Manufacturing PMI",
        "s&p global services pmi": "S&P Global Services PMI",
        "fed interest rate decision": "Federal Funds Rate",
        "interest rate": "Federal Funds Rate",
        "fomc economic projections": "FOMC Economic Projections",
        "fed press conference": "FOMC Press Conference"
    }
    return mapping.get(tl)

def fetch_from_tradingview_calendar() -> List[Dict[str, Any]]:
    """Fetches past 12 days (for actuals memory) and upcoming 35 days of official US economic calendar events from TradingView."""
    now = datetime.now(timezone.utc)
    windows = [
        (now - timedelta(days=12), now + timedelta(days=2)),
        (now + timedelta(days=2), now + timedelta(days=18)),
        (now + timedelta(days=18), now + timedelta(days=35)),
    ]

    raw_events = []
    for w_start, w_end in windows:
        start_str = w_start.strftime("%Y-%m-%dT00:00:00.000Z")
        end_str = w_end.strftime("%Y-%m-%dT00:00:00.000Z")
        url = f"{TRADINGVIEW_CALENDAR_URL}?from={urllib.parse.quote(start_str)}&to={urllib.parse.quote(end_str)}&countries=US"
        try:
            req = urllib.request.Request(url, headers=TV_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_events.extend(data.get("result", []))
        except Exception as e:
            print(f"[CalendarService] TradingView window fetch warning ({start_str[:10]}): {e}")

    mapped = []
    for e in raw_events:
        imp_num = e.get("importance", -1)
        if imp_num < 0:
            continue

        raw_title = (e.get("title") or "").strip()
        canonical_title = _map_tradingview_title(raw_title)
        if not canonical_title:
            continue

        date_str = e.get("date")
        if not date_str:
            continue
        try:
            dt = parse_utc_datetime(date_str).replace(second=0, microsecond=0)
        except Exception:
            continue

        unit = e.get("unit")
        scale = e.get("scale")
        # Default scale 'K' for Non-Farm Employment Change if TradingView omits unit/scale on raw payrolls count
        if canonical_title == "Non-Farm Employment Change" and not scale and not unit:
            scale = "K"
        elif canonical_title in ["Core CPI m/m", "Core CPI y/y", "CPI m/m", "CPI y/y", "Core PPI m/m", "Core PPI y/y", "PPI m/m", "PPI y/y", "Unemployment Rate", "Average Hourly Earnings m/m", "Average Hourly Earnings y/y", "Federal Funds Rate"] and not unit:
            unit = "%"

        forecast = _format_tv_figure(e.get("forecast"), unit, scale)
        previous = _format_tv_figure(e.get("previous"), unit, scale)
        actual_val = e.get("actual")
        actual = _format_tv_figure(actual_val, unit, scale) if actual_val is not None and actual_val != "" else ""

        impact = "High" if imp_num >= 1 else "Medium"

        mapped.append({
            "title": canonical_title,
            "country": "USD",
            "date": dt.isoformat(),
            "impact": impact,
            "forecast": forecast,
            "previous": previous,
            "actual": actual
        })
    return mapped

def _normalize_dedup_title(title: str) -> str:
    """Produces a normalized key for deduplicating identical indicators across feeds."""
    t = title.strip().lower()
    synonyms = {
        "initial jobless claims": "unemployment claims",
        "jobless claims": "unemployment claims",
        "non farm payrolls": "non-farm employment change",
        "non-farm payrolls": "non-farm employment change",
        "non-farm employment change (nfp)": "non-farm employment change",
        "inflation rate mom": "cpi m/m",
        "inflation rate yoy": "cpi y/y",
        "core inflation rate mom": "core cpi m/m",
        "core inflation rate yoy": "core cpi y/y",
        "ppi mom": "ppi m/m",
        "core ppi mom": "core ppi m/m",
        "retail sales mom": "retail sales m/m",
        "core retail sales mom": "core retail sales m/m",
    }
    return synonyms.get(t, t)

def fetch_raw_events() -> List[Dict[str, Any]]:
    """Multi-source resilient fetcher: ForexFactory (XML/JSON) merged with TradingView (multi-week upcoming)."""
    all_events: List[Dict[str, Any]] = []
    seen_by_key: Dict[tuple, Dict[str, Any]] = {}

    def _add_or_merge_event(ev: Dict[str, Any]):
        try:
            dt = parse_utc_datetime(ev["date"]).replace(second=0, microsecond=0)
        except Exception:
            return
        ev["date"] = dt.isoformat()
        norm_title = _normalize_dedup_title(ev.get("title", ""))
        key = (dt.strftime("%Y-%m-%dT%H:%M"), norm_title)
        if key not in seen_by_key:
            seen_by_key[key] = ev
            all_events.append(ev)
        else:
            existing = seen_by_key[key]
            if (existing.get("forecast") in ["-", "", None]) and ev.get("forecast") not in ["-", "", None]:
                existing["forecast"] = ev["forecast"]
            if (existing.get("previous") in ["-", "", None]) and ev.get("previous") not in ["-", "", None]:
                existing["previous"] = ev["previous"]
            if not existing.get("actual") and ev.get("actual"):
                existing["actual"] = ev["actual"]

    # 1. Primary: ForexFactory XML, falling back to ForexFactory JSON
    ff_loaded = False
    try:
        evs = fetch_from_forexfactory_xml()
        for e in evs:
            _add_or_merge_event(e)
        if evs:
            ff_loaded = True
            print(f"[CalendarService] Successfully loaded {len(evs)} USD events from ForexFactory XML.")
    except Exception as e:
        print(f"[CalendarService] ForexFactory XML unavailable: {e}")

    if not ff_loaded:
        try:
            evs_json = fetch_from_forexfactory_json()
            for e in evs_json:
                _add_or_merge_event(e)
            if evs_json:
                print(f"[CalendarService] Successfully loaded {len(evs_json)} USD events from ForexFactory JSON.")
        except Exception as e2:
            print(f"[CalendarService] ForexFactory JSON unavailable: {e2}")

    # 2. Multi-week upcoming complement & backup: TradingView Economic Calendar API
    try:
        before_count = len(all_events)
        evs_tv = fetch_from_tradingview_calendar()
        for e in evs_tv:
            _add_or_merge_event(e)
        added_tv = len(all_events) - before_count
        if evs_tv:
            print(f"[CalendarService] Loaded {added_tv} additional multi-week USD events from TradingView Calendar.")
    except Exception as e:
        print(f"[CalendarService] TradingView Calendar backup unavailable: {e}")

    return all_events

GROUP_PRIORITY = {
    "NFP": 100,
    "FOMC": 95,
    "CPI": 90,
    "PPI": 80,
    "PMI": 75,
    "NFP_COMPONENT": 10
}

def group_events_by_time(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups events happening at the same datetime and assigns one of the 5 allowed canonical group names (NFP, PPI, CPI, FOMC, PMI)."""
    grouped: Dict[str, Dict[str, Any]] = {}
    now = datetime.now(timezone.utc)

    for ev in events:
        try:
            ev_time = parse_utc_datetime(ev["date"]).replace(second=0, microsecond=0)
        except Exception:
            continue

        time_key = ev_time.isoformat()
        ev_title = ev.get("title", "USD News")
        candidate_group = classify_event_group(ev_title)
        if not candidate_group:
            continue

        if time_key not in grouped:
            grouped[time_key] = {
                "group_name": candidate_group,
                "datetime": time_key,
                "datetime_wib": format_wib_datetime(time_key),
                "timestamp": int(ev_time.timestamp()),
                "is_past": ev_time < now,
                "seconds_until": int((ev_time - now).total_seconds()),
                "items": []
            }
        else:
            curr_group = grouped[time_key]["group_name"]
            if GROUP_PRIORITY.get(candidate_group, 0) > GROUP_PRIORITY.get(curr_group, 0):
                grouped[time_key]["group_name"] = candidate_group

        # Prevent duplicate items inside the same timestamp cluster
        norm_item_title = _normalize_dedup_title(ev_title)
        existing_items = grouped[time_key]["items"]
        duplicate_item = next(
            (it for it in existing_items if _normalize_dedup_title(it.get("title", "")) == norm_item_title),
            None
        )
        if duplicate_item:
            if duplicate_item.get("forecast") in ["-", "", None] and ev.get("forecast") not in ["-", "", None]:
                duplicate_item["forecast"] = ev.get("forecast")
            if duplicate_item.get("previous") in ["-", "", None] and ev.get("previous") not in ["-", "", None]:
                duplicate_item["previous"] = ev.get("previous")
            if not duplicate_item.get("actual") and ev.get("actual"):
                duplicate_item["actual"] = ev.get("actual")
        else:
            existing_items.append({
                "title": ev_title,
                "impact": ev.get("impact", "High"),
                "forecast": ev.get("forecast", "-") or "-",
                "previous": ev.get("previous", "-") or "-",
                "actual": ev.get("actual", "") or ""
            })

    # Sort chronologically and strictly retain ONLY the 5 allowed groups (NFP, PPI, CPI, FOMC, PMI)
    sorted_clusters = [
        c for c in sorted(grouped.values(), key=lambda x: x["timestamp"])
        if c["group_name"] in ALLOWED_GROUPS
    ]

    # Deduplicate same-day clusters that have the exact same major group_name
    deduped_clusters: List[Dict[str, Any]] = []
    seen_day_groups: Dict[tuple, Dict[str, Any]] = {}

    for cluster in sorted_clusters:
        g_name = cluster["group_name"]
        day_str = cluster["datetime"][:10]
        if g_name in ALLOWED_GROUPS:
            day_key = (day_str, g_name)
            if day_key in seen_day_groups:
                primary = seen_day_groups[day_key]
                for it in cluster["items"]:
                    norm_t = _normalize_dedup_title(it.get("title", ""))
                    if not any(_normalize_dedup_title(p_it.get("title", "")) == norm_t for p_it in primary["items"]):
                        primary["items"].append(it)
                continue
            seen_day_groups[day_key] = cluster
        deduped_clusters.append(cluster)

    def _item_sort_priority(it: Dict[str, Any]) -> int:
        tl = it.get("title", "").lower()
        if "non-farm" in tl or "payrolls" in tl:
            return 0
        if "unemployment rate" in tl:
            return 1
        if "average hourly earnings m/m" in tl:
            return 2
        if "core" in tl and "m/m" in tl:
            return 3
        if "m/m" in tl:
            return 4
        if it.get("impact") == "High":
            return 5
        return 6

    for cluster in deduped_clusters:
        cluster["items"].sort(key=_item_sort_priority)

    return deduped_clusters

def get_economic_calendar(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns parsed economic calendar filtered strictly to NFP, PPI, CPI, FOMC, PMI.
    Enforces the H-3 (3 days = 259,200s) rule: if no allowed news is within 3 days,
    returns 'WAITING NEWS' as the active reading.
    """
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    raw_events = []
    cache_time = 0
    cached_raw = []

    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cache_time = cached.get("cached_at", 0)
                cached_raw = [e for e in cached.get("raw_events", []) if is_high_impact_event(e)]
        except Exception as e:
            print(f"[CalendarService] Cache read error: {e}")

    # Check if cached events are still fresh (within 1800s = 30m, or 60s cooldown on force_refresh to avoid 429)
    cache_ttl = 60 if force_refresh else 1800
    if cached_raw and (now.timestamp() - cache_time < cache_ttl):
        has_future = any(
            parse_utc_datetime(e["date"]).timestamp() > now.timestamp()
            for e in cached_raw if "date" in e
        )
        has_recent_past_actuals = any(
            parse_utc_datetime(e["date"]).timestamp() <= now.timestamp() and bool(e.get("actual"))
            for e in cached_raw if "date" in e
        )
        if has_future and has_recent_past_actuals:
            raw_events = cached_raw

    if not raw_events:
        fetched = fetch_raw_events()
        high_impact = [e for e in fetched if is_high_impact_event(e)]
        if high_impact:
            raw_events = high_impact
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "cached_at": int(now.timestamp()),
                        "raw_events": raw_events
                    }, f, indent=2)
            except Exception as e:
                print(f"[CalendarService] Cache write error: {e}")
        elif cached_raw:
            raw_events = cached_raw

    grouped = group_events_by_time(raw_events)

    # Recalculate seconds_until and status
    upcoming_clusters = []
    past_clusters = []

    for g in grouped:
        ev_dt = datetime.fromtimestamp(g["timestamp"], tz=timezone.utc)
        diff_sec = int((ev_dt - now).total_seconds())
        g["seconds_until"] = diff_sec
        g["is_past"] = diff_sec < 0
        g["datetime_wib"] = format_wib_datetime(g["datetime"])
        g["is_within_h3"] = (0 < diff_sec <= H3_WINDOW_SECONDS)

        if diff_sec > 0:
            days = diff_sec // 86400
            hours = (diff_sec % 86400) // 3600
            minutes = (diff_sec % 3600) // 60
            seconds = diff_sec % 60

            if days > 0:
                g["countdown_str"] = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                g["countdown_str"] = f"{hours}h {minutes}m {seconds}s"
            else:
                g["countdown_str"] = f"{minutes}m {seconds}s"
            upcoming_clusters.append(g)
        else:
            g["countdown_str"] = "Released"
            past_clusters.append(g)

    first_upcoming = upcoming_clusters[0] if upcoming_clusters else None

    # Enforce H-3 (3 Days = 259,200 seconds) Rule:
    # If there is an allowed event within 3 days, activate it and release H-3 analysis.
    # Otherwise, set active reading to WAITING NEWS until H-3 before the next allowed event.
    if first_upcoming and first_upcoming["seconds_until"] <= H3_WINDOW_SECONDS:
        next_event = dict(first_upcoming)
        next_event["is_waiting"] = False
        next_event["h3_active"] = True
    else:
        next_sched_group = first_upcoming["group_name"] if first_upcoming else None
        next_sched_wib = first_upcoming["datetime_wib"] if first_upcoming else None
        seconds_to_h3 = max(0, first_upcoming["seconds_until"] - H3_WINDOW_SECONDS) if first_upcoming else 0
        next_event = {
            "group_name": "WAITING NEWS",
            "is_waiting": True,
            "h3_active": False,
            "datetime": first_upcoming["datetime"] if first_upcoming else "",
            "datetime_wib": (
                f"Tidak ada news 3 hari ke depan • Berikutnya: {next_sched_group} ({next_sched_wib})"
                if first_upcoming else "Tidak ada jadwal NFP / PPI / CPI / FOMC / PMI dalam 3 hari ke depan"
            ),
            "timestamp": first_upcoming["timestamp"] if first_upcoming else 0,
            "is_past": False,
            "seconds_until": first_upcoming["seconds_until"] if first_upcoming else 0,
            "seconds_until_h3": seconds_to_h3,
            "countdown_str": first_upcoming["countdown_str"] if first_upcoming else "Waiting News",
            "next_scheduled_group": next_sched_group,
            "next_scheduled_wib": next_sched_wib,
            "items": []
        }

    return {
        "next_event": next_event,
        "upcoming_events": upcoming_clusters[:12],
        "past_events": past_clusters[-8:],
        "correlated_news": get_correlated_lead_news(
            next_event.get("group_name", "") if next_event else "",
            past_clusters[-8:]
        ),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

def _build_past_actuals_card(past_events: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Builds a live summary card of the most recent released NFP, CPI, PPI, PMI, or FOMC actual figures."""
    if not past_events:
        return None
    recent_summaries = []
    hawkish_hits = 0
    dovish_hits = 0
    for ev in reversed(past_events):
        g_name = ev.get("group_name", "")
        items_with_actual = [it for it in ev.get("items", []) if it.get("actual") and it.get("actual") != "-"]
        if not items_with_actual:
            continue
        item_strs = []
        for it in items_with_actual[:3]:
            t = it.get("title", "")
            a = it.get("actual", "-")
            f = it.get("forecast", "-")
            item_strs.append(f"{t}: Actual {a} (vs Forecast {f})")
            try:
                a_num = float(str(a).replace("%", "").replace("K", "").replace("M", "").replace("B", "").strip())
                f_num = float(str(f).replace("%", "").replace("K", "").replace("M", "").replace("B", "").strip())
                if "unemployment rate" in t.lower():
                    if a_num < f_num:
                        hawkish_hits += 1
                    elif a_num > f_num:
                        dovish_hits += 1
                else:
                    if a_num > f_num:
                        hawkish_hits += 1
                    elif a_num < f_num:
                        dovish_hits += 1
            except Exception:
                pass
        recent_summaries.append(f"[{g_name}] " + ", ".join(item_strs))
        if len(recent_summaries) >= 2:
            break

    if not recent_summaries:
        return None

    if hawkish_hits > dovish_hits:
        impact_type = "sell"
        status_lbl = "Data Aktual Sebelumnya Panas (Hawkish USD)"
        bias_lbl = "Bearish XAU / Tekanan Jual Lanjutan (SELL)"
    elif dovish_hits > hawkish_hits:
        impact_type = "buy"
        status_lbl = "Data Aktual Sebelumnya Melandai (Dovish USD)"
        bias_lbl = "Bullish XAU / Dorongan Beli Lanjutan (BUY)"
    else:
        impact_type = "neutral"
        status_lbl = "Data Aktual Sebelumnya Seimbang"
        bias_lbl = "Netral / Menunggu Konfirmasi"

    return {
        "title": "Rekam Jejak Data Aktual Terakhir (NFP & CPI Siklus Berjalan)",
        "category": "Korelasi Aktual",
        "status": status_lbl,
        "latest_data": " • ".join(recent_summaries),
        "relation_note": "Hasil aktual berita High Impact sebelumnya menentukan rezim makroekonomi berjalan. Ketika NFP/Upah dan CPI aktual keluar di atas Forecast (panas), angka Forecast rendah pada rilis berikutnya rawan meleset naik (upside surprise).",
        "bias_impact": bias_lbl,
        "impact_type": impact_type,
        "importance": "Pemberat Utama (45% Bobot)"
    }

def get_correlated_lead_news(main_group: str, past_events: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Returns secondary/lead-in indicators tailored specifically to the 5 allowed major news events (or WAITING NEWS)."""
    mg = main_group.strip().upper()
    past_card = _build_past_actuals_card(past_events)

    if mg == "WAITING NEWS" or not mg:
        return [
            {
                "title": "Protokol H-3 Kalender High Impact (NFP • PPI • CPI • FOMC • PMI)",
                "category": "Protokol Sistem",
                "status": "Mode Standby (Waiting News)",
                "latest_data": "Menunggu Jendela H-3 (72 Jam Sebelum Rilis)",
                "relation_note": "Saat tidak ada jadwal rilis NFP, PPI, CPI, FOMC, atau PMI dalam 3 hari ke depan, terminal berada pada mode WAITING NEWS. Hasil analisa AI Quant akan keluar otomatis tepat pada H-3 sebelum rilis berita.",
                "bias_impact": "Fokus pada struktur teknikal & berita harian makro",
                "impact_type": "neutral",
                "importance": "Aturan H-3 Aktif"
            },
            {
                "title": "US 10-Year Treasury Yield & Dollar Index (DXY)",
                "category": "Pasar Obligasi & Valas",
                "status": "Barometer Intermarket Harian",
                "latest_data": "Korelasi Terbalik dengan XAU/USD",
                "relation_note": "Di luar jendela H-3 berita kalender, pergerakan emas spot (XAU/USD) dikendalikan oleh fluktuasi imbal hasil obligasi AS 10 tahun dan aliran safe-haven geopolitik.",
                "bias_impact": "Bullish XAU saat Yield & DXY melemah",
                "impact_type": "buy",
                "importance": "Tinggi (50% Bobot)"
            },
            {
                "title": "Arus Geopolitik & Permintaan Bank Sentral",
                "category": "Safe-Haven",
                "status": "Pemantauan Real-Time",
                "latest_data": "Pantau Tab Berita Harian",
                "relation_note": "Eskalasi geopolitik atau pernyataan mendadak pejabat bank sentral dapat memicu volatilitas intraday meskipun sedang tidak ada rilis kalender dalam 3 hari ke depan.",
                "bias_impact": "Pantau buletin makro harian di Tab 3",
                "impact_type": "neutral",
                "importance": "Tinggi (50% Bobot)"
            }
        ]

    elif mg == "NFP":
        base_cards = [
            {
                "title": "Non-Farm Employment Change (Penciptaan Lapangan Kerja AS)",
                "category": "Tenaga Kerja Utama",
                "status": "Komponen Inti NFP",
                "latest_data": "Pantau Deviasi Aktual vs Konsensus",
                "relation_note": "Mengukur perubahan jumlah tenaga kerja di luar sektor pertanian. Deviasi >25K-30K dari konsensus memicu lonjakan volatilitas instan pada DXY dan XAU/USD.",
                "bias_impact": "Hawkish USD / Bearish XAU jika di atas konsensus",
                "impact_type": "sell",
                "importance": "Sangat Tinggi (45% Bobot)"
            },
            {
                "title": "Average Hourly Earnings m/m & y/y (Pertumbuhan Upah)",
                "category": "Inflasi Upah",
                "status": "Pemicu Inflasi Jasa",
                "latest_data": "Komponen Utama Laporan NFP",
                "relation_note": "Kenaikan upah rata-rata per jam adalah bahan bakar utama inflasi jasa (sticky inflation). Jika upah naik tajam, The Fed enggan memangkas suku bunga secara agresif.",
                "bias_impact": "Hawkish USD / Bearish XAU jika naik",
                "impact_type": "sell",
                "importance": "Tinggi (30% Bobot)"
            },
            {
                "title": "Unemployment Rate (Tingkat Pengangguran AS)",
                "category": "Mandat Ketenagakerjaan",
                "status": "Mandat Ganda The Fed",
                "latest_data": "Acuan Stabilitas Pasar Kerja",
                "relation_note": "Jika tingkat pengangguran naik melampaui konsensus, pasar akan memperkuat spekulasi pemangkasan suku bunga The Fed, memicu lonjakan pembelian emas.",
                "bias_impact": "Dovish USD / Bullish XAU jika pengangguran naik",
                "impact_type": "buy",
                "importance": "Tinggi (25% Bobot)"
            }
        ]

    elif mg == "CPI":
        base_cards = [
            {
                "title": "Core CPI m/m & y/y (Inflasi Inti Tanpa Pangan & Energi)",
                "category": "Inflasi Inti",
                "status": "Fokus Utama Komite FOMC",
                "latest_data": "Metrik Prioritas The Fed",
                "relation_note": "Core CPI mencerminkan inflasi persisten. Deviasi 0.1% saja pada Core CPI m/m dapat mengubah ekspektasi suku bunga The Fed dan menggerakkan XAU/USD secara tajam.",
                "bias_impact": "Hawkish USD / Bearish XAU jika > Forecast",
                "impact_type": "sell",
                "importance": "Sangat Tinggi (40% Bobot)"
            },
            {
                "title": "Headline CPI & Harga Energi (Minyak Mentah)",
                "category": "Inflasi Umum",
                "status": "Penggerak Ekspektasi Inflasi",
                "latest_data": "Sensitif Terhadap Harga Energi",
                "relation_note": "Penurunan Headline CPI akibat melandainya biaya energi memperkuat narasi disinflasi, menekan imbal hasil riil obligasi AS dan menopang kenaikan harga emas.",
                "bias_impact": "Dovish USD / Bullish XAU jika < Forecast",
                "impact_type": "buy",
                "importance": "Tinggi (35% Bobot)"
            },
            {
                "title": "US 10-Year Treasury Yield & Dollar Index (DXY)",
                "category": "Pasar Obligasi",
                "status": "Transmisi Imbal Hasil Riil",
                "latest_data": "Korelasi Terbalik dengan XAU/USD",
                "relation_note": "Kenaikan inflasi mendorong imbal hasil obligasi AS naik dan menekan emas, sedangkan inflasi yang melandai memicu penurunan yield dan reli XAU/USD.",
                "bias_impact": "Bearish XAU saat Yield & DXY melonjak",
                "impact_type": "sell",
                "importance": "Sedang (25% Bobot)"
            }
        ]

    elif mg == "PPI":
        base_cards = [
            {
                "title": "Core PPI m/m (Inflasi Produsen Inti)",
                "category": "Inflasi Hulu",
                "status": "Indikator Biaya Produksi",
                "latest_data": "Komponen Input PCE",
                "relation_note": "Biaya produsen inti mengalir langsung ke perhitungan Core PCE (indikator inflasi favorit The Fed). Namun jika NFP & CPI sebelumnya keluar panas, PPI m/m >= 0.3% tetap menandakan inflasi hulu yang lengket.",
                "bias_impact": "Hawkish USD / Bearish XAU jika >= 0.3% atau > Forecast",
                "impact_type": "sell",
                "importance": "Sangat Tinggi (40% Bobot)"
            },
            {
                "title": "Transmisi CPI & Margin Korporasi AS",
                "category": "Rantai Pasok",
                "status": "Leading Indicator Inflasi Konsumen",
                "latest_data": "Pantau Deviasi m/m",
                "relation_note": "Lonjakan PPI mengindikasikan kenaikan biaya di tingkat pabrik yang akan dibebankan ke konsumen dalam 1-2 bulan berikutnya.",
                "bias_impact": "Hawkish USD / Bearish XAU jika > Forecast",
                "impact_type": "sell",
                "importance": "Tinggi (35% Bobot)"
            },
            {
                "title": "US 10-Year Treasury Yield & Dollar Index (DXY)",
                "category": "Pasar Obligasi",
                "status": "Reaksi Suku Bunga",
                "latest_data": "Konfirmasi Arah Sesi New York",
                "relation_note": "Respon langsung pasar obligasi terhadap rilis PPI menentukan apakah pergerakan awal emas akan berlanjut searah (one-way) atau berbalik.",
                "bias_impact": "Bearish XAU saat Yield bertahan tinggi pasca CPI",
                "impact_type": "sell",
                "importance": "Sedang (25% Bobot)"
            }
        ]

    elif mg == "PMI":
        base_cards = [
            {
                "title": "ISM Services & Manufacturing PMI (Ambang Ekspansi 50.0)",
                "category": "Aktivitas Ekonomi",
                "status": "Indikator Siklus Bisnis AS",
                "latest_data": "Batas Kritis Ekspansi vs Kontraksi: 50.0",
                "relation_note": "Angka PMI di atas 50.0 menandakan ekspansi ekonomi yang menopang Dolar AS, sedangkan angka di bawah 50.0 mengindikasikan kontraksi dan memicu reli emas.",
                "bias_impact": "Dovish USD / Bullish XAU jika PMI < Forecast",
                "impact_type": "buy",
                "importance": "Sangat Tinggi (45% Bobot)"
            },
            {
                "title": "Flash Manufacturing & Services PMI (S&P Global)",
                "category": "Leading Indicator PMI",
                "status": "Survei Manajer Pembelian Awal",
                "latest_data": "Barometer Pesanan Baru & Output",
                "relation_note": "Memberikan gambaran awal kondisi manufaktur dan jasa AS setiap bulan sebelum rilis ISM, sangat sensitif terhadap ekspektasi pertumbuhan PDB.",
                "bias_impact": "Hawkish USD / Bearish XAU jika > Forecast",
                "impact_type": "sell",
                "importance": "Tinggi (30% Bobot)"
            },
            {
                "title": "US 10-Year Treasury Yield & Dollar Index (DXY)",
                "category": "Intermarket",
                "status": "Respon Likuiditas New York",
                "latest_data": "Korelasi Negatif XAU/USD",
                "relation_note": "Pelemahan PMI yang diikuti penurunan yield US 10Y menjadi konfirmasi kuat bagi akumulasi beli XAU/USD di sesi New York.",
                "bias_impact": "Bullish XAU saat Yield turun pasca PMI lemah",
                "impact_type": "buy",
                "importance": "Sedang (25% Bobot)"
            }
        ]

    else:  # FOMC
        base_cards = [
            {
                "title": "CME FedWatch Tool (Probabilitas Target Suku Bunga)",
                "category": "Ekspektasi Pasar",
                "status": "Priced-in Suku Bunga",
                "latest_data": "Pantau Pergeseran Probabilitas Rate",
                "relation_note": "Perubahan probabilitas pada suku bunga The Fed secara langsung menentukan arah likuiditas global dan valuasi emas dunia.",
                "bias_impact": "Hawkish USD / Bearish XAU jika rate dipertahankan tinggi",
                "impact_type": "sell",
                "importance": "Sangat Tinggi (40% Bobot)"
            },
            {
                "title": "FOMC Statement & Dot Plot (Economic Projections)",
                "category": "Kebijakan Moneter",
                "status": "Panduan Suku Bunga The Fed",
                "latest_data": "Jangkar Proyeksi Moneter",
                "relation_note": "Pernyataan resmi FOMC dan proyeksi suku bunga (Dot Plot) menjadi penentu utama tren menengah Dolar AS dan XAU/USD.",
                "bias_impact": "Bullish XAU jika proyeksi suku bunga dipangkas",
                "impact_type": "buy",
                "importance": "Tinggi (35% Bobot)"
            },
            {
                "title": "US 10Y Treasury Yields & DXY",
                "category": "Intermarket & Obligasi",
                "status": "Biaya Oportunitas Emas",
                "latest_data": "Korelasi Negatif XAU/USD",
                "relation_note": "Imbal hasil obligasi AS meningkat seiring sikap hawkish The Fed, menekan daya tarik emas sebagai aset tanpa yield.",
                "bias_impact": "Bearish XAU / Bullish USD saat yield naik",
                "impact_type": "sell",
                "importance": "Tinggi (25% Bobot)"
            }
        ]

    if past_card:
        return [past_card] + base_cards
    return base_cards
