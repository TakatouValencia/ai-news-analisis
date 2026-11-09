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

def classify_event_group(title: str) -> str:
    """Maps a raw USD economic indicator title to its canonical institutional event group without false positives."""
    t = title.strip().lower()

    # 1. Speeches & Testimonies (Never classify speeches as FOMC Rate Decision or NFP)
    if is_speech_or_testimony(t):
        if any(w in t for w in ["chair", "powell", "warsh"]):
            return "Fed Chair Speech"
        return title.strip()

    # 2. FOMC Meeting Minutes vs Official FOMC Rate Decision
    if "fomc meeting minutes" in t or "fomc minutes" in t or ("minutes" in t and "fomc" in t):
        return "FOMC Meeting Minutes"
    if "fomc press conference" in t:
        return "FOMC Press Conference"
    if any(w in t for w in ["federal funds rate", "fomc statement", "fomc economic projections", "fed interest rate", "interest rate decision"]) or t == "interest rate":
        return "FOMC"

    # 3. ADP Employment vs Official BLS Non-Farm Payrolls (NFP)
    if "adp" in t:
        return "ADP Non-Farm Employment"
    if (
        ("non-farm" in t or "non farm" in t or "nfp" in t or "jobs report" in t or "payrolls" in t)
        and "adp" not in t
        and "productivity" not in t
        and "weekly" not in t
    ):
        return "NFP"

    # 4. Other Labor Market Releases
    if "unemployment claims" in t or "jobless claims" in t or "initial claims" in t:
        return "Initial Jobless Claims"
    if "unemployment rate" in t:
        return "Unemployment Rate"
    if "average hourly earnings" in t:
        return "Average Hourly Earnings"
    if "jolts" in t or "job openings" in t:
        return "JOLTS Job Openings"
    if "employment cost index" in t:
        return "Employment Cost Index"

    # 5. Inflation Releases (CPI, PPI, Core PCE)
    if ("cpi" in t or "inflation rate" in t) and "expectation" not in t:
        return "CPI"
    if "ppi" in t or "producer price" in t:
        return "PPI"
    if "pce" in t:
        return "Core PCE"

    # 6. Growth, Activity & Sentiment
    if "retail sales" in t and "inventories" not in t:
        return "Retail Sales"
    if "gdp" in t:
        return "GDP"
    if "ism" in t and ("pmi" in t or "manufacturing" in t or "services" in t or "prices" in t):
        return "ISM PMI"
    if "consumer confidence" in t or "consumer sentiment" in t:
        return "Consumer Confidence"

    return title.strip()

def is_high_impact_event(event: Dict[str, Any]) -> bool:
    """Strictly filters for genuine High Impact USD market-moving macroeconomic releases."""
    if event.get("country") != "USD":
        return False

    impact = str(event.get("impact", "")).strip().lower()
    title = str(event.get("title", "")).strip().lower()

    if impact in ["low", "holiday", ""]:
        return False

    # Exclude routine FOMC member speeches and low/medium noise
    if is_speech_or_testimony(title):
        if "fomc member" in title or impact != "high":
            return False
        # Only allow High-impact Fed Chair speeches/testimonies
        return any(w in title for w in ["chair", "powell", "warsh"])

    # Exclude minor/weekly/regional reports that are never Tier-1 catalysts
    excluded_phrases = [
        "weekly", "auction", "inventories", "storage", "rig count",
        "mba ", "nahb", "philly fed", "philadelphia fed", "richmond fed",
        "chicago fed", "empire state", "challenger", "export sales",
        "wasde", "budget", "delinquencies", "cpi-w", "nsa", "seasonally adjusted",
        "machinery manufacturing", "existing home sales", "new home sales",
        "pending home sales", "housing starts", "building permits", "durable goods"
    ]
    if any(ex in title for ex in excluded_phrases):
        return False

    # Red folder / High impact
    if impact == "high":
        return True

    # Medium impact: ONLY allow core macroeconomic releases that some feeds classify as Medium
    if impact == "medium":
        allowed_medium_exact = [
            "unemployment claims",
            "initial jobless claims",
            "jobless claims",
            "core cpi m/m",
            "core cpi y/y",
            "cpi m/m",
            "cpi y/y",
            "core ppi m/m",
            "core ppi y/y",
            "ppi m/m",
            "ppi y/y",
            "core pce price index m/m",
            "core pce price index y/y",
            "non-farm employment change",
            "adp non-farm employment change",
            "unemployment rate",
            "average hourly earnings m/m",
            "federal funds rate",
            "fomc statement",
            "fomc meeting minutes",
            "advance gdp q/q",
            "prelim gdp q/q",
            "final gdp q/q",
            "retail sales m/m",
            "core retail sales m/m",
            "ism manufacturing pmi",
            "ism services pmi",
            "jolts job openings"
        ]
        if any(kw in title for kw in allowed_medium_exact):
            return True

    return False

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
    """Maps TradingView economic calendar indicator names to canonical ForexFactory-compatible USD titles."""
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
        "adp employment change": "ADP Non-Farm Employment Change",
        "unemployment rate": "Unemployment Rate",
        "average hourly earnings mom": "Average Hourly Earnings m/m",
        "average hourly earnings yoy": "Average Hourly Earnings y/y",
        "initial jobless claims": "Unemployment Claims",
        "jolts job openings": "JOLTS Job Openings",
        "retail sales mom": "Retail Sales m/m",
        "retail sales ex autos mom": "Core Retail Sales m/m",
        "core pce price index mom": "Core PCE Price Index m/m",
        "core pce price index yoy": "Core PCE Price Index y/y",
        "ism manufacturing pmi": "ISM Manufacturing PMI",
        "ism services pmi": "ISM Services PMI",
        "fed interest rate decision": "Federal Funds Rate",
        "interest rate": "Federal Funds Rate",
        "fomc minutes": "FOMC Meeting Minutes",
        "fomc economic projections": "FOMC Economic Projections",
        "fed press conference": "FOMC Press Conference"
    }
    if tl in mapping:
        return mapping[tl]
    if tl.startswith("gdp growth rate qoq"):
        if "adv" in tl:
            return "Advance GDP q/q"
        if "2nd" in tl or "prelim" in tl:
            return "Prelim GDP q/q"
        return "Final GDP q/q"
    return None

def fetch_from_tradingview_calendar() -> List[Dict[str, Any]]:
    """Fetches multi-week official US economic calendar events from TradingView to ensure continuous upcoming coverage."""
    now = datetime.now(timezone.utc)
    start_str = (now - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = (now + timedelta(days=35)).strftime("%Y-%m-%dT00:00:00.000Z")
    url = f"{TRADINGVIEW_CALENDAR_URL}?from={urllib.parse.quote(start_str)}&to={urllib.parse.quote(end_str)}&countries=US"

    req = urllib.request.Request(url, headers=TV_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        raw_events = data.get("result", [])

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
    "FOMC Press Conference": 92,
    "CPI": 90,
    "Core PCE": 85,
    "FOMC Meeting Minutes": 82,
    "GDP": 80,
    "PPI": 75,
    "Retail Sales": 70,
    "ISM PMI": 65,
    "JOLTS Job Openings": 60,
    "ADP Non-Farm Employment": 58,
    "Initial Jobless Claims": 55,
    "Unemployment Rate": 52,
    "Average Hourly Earnings": 51,
    "Consumer Confidence": 50,
    "Fed Chair Speech": 45
}

def group_events_by_time(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups events happening at the same datetime and assigns the exact canonical group name."""
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
            if GROUP_PRIORITY.get(candidate_group, 10) > GROUP_PRIORITY.get(curr_group, 10):
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

    # Sort chronologically
    sorted_clusters = sorted(grouped.values(), key=lambda x: x["timestamp"])

    # Deduplicate same-day clusters that have the exact same major group_name
    # (e.g., if two feeds reported the same release with a 1-hour DST offset on the same date)
    deduped_clusters: List[Dict[str, Any]] = []
    seen_day_groups: Dict[tuple, Dict[str, Any]] = {}
    unique_daily_groups = {
        "NFP", "FOMC", "FOMC Meeting Minutes", "CPI", "PPI", "Core PCE",
        "GDP", "Retail Sales", "Initial Jobless Claims", "ADP Non-Farm Employment",
        "ISM PMI", "JOLTS Job Openings"
    }

    for cluster in sorted_clusters:
        g_name = cluster["group_name"]
        day_str = cluster["datetime"][:10]
        if g_name in unique_daily_groups:
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

    return deduped_clusters

def get_economic_calendar(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns parsed economic calendar and the next high-impact USD news cluster."""
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
        if has_future:
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

    next_event = upcoming_clusters[0] if upcoming_clusters else None

    return {
        "next_event": next_event,
        "upcoming_events": upcoming_clusters[:12],
        "past_events": past_clusters[-5:],
        "correlated_news": get_correlated_lead_news(next_event.get("group_name", "") if next_event else ""),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

def get_correlated_lead_news(main_group: str) -> List[Dict[str, Any]]:
    """Returns secondary/lead-in indicators tailored specifically to the upcoming major news event."""
    mg = main_group.strip().upper()

    if mg == "NFP" or "ADP" in mg:
        return [
            {
                "title": "ADP Non-Farm Employment Change (Sektor Swasta)",
                "category": "Tenaga Kerja Swasta",
                "status": "Leading Indicator NFP",
                "latest_data": "Pantau Deviasi Aktual vs Konsensus",
                "relation_note": "ADP mengukur penambahan tenaga kerja sektor swasta 2 hari sebelum NFP. Angka di atas ekspektasi mengindikasikan payrolls NFP kuat dan memicu reli Dolar AS.",
                "bias_impact": "Hawkish USD / Bearish XAU jika di atas konsensus",
                "impact_type": "sell",
                "importance": "Sangat Tinggi (35% Bobot)"
            },
            {
                "title": "Average Hourly Earnings m/m & y/y (Pertumbuhan Upah)",
                "category": "Inflasi Upah",
                "status": "Pemicu Inflasi Jasa",
                "latest_data": "Komponen Utama Laporan Tenaga Kerja",
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
            },
            {
                "title": "Initial Jobless Claims (Klaim Pengangguran Mingguan)",
                "category": "Klaim Mingguan",
                "status": "Indikator Frekuensi Tinggi",
                "latest_data": "Rilis Rutin Hari Kamis",
                "relation_note": "Klaim pengangguran yang rendah menunjukkan gelombang PHK masih minim di perusahaan AS, memberikan bantalan bagi The Fed untuk menjaga suku bunga ketat.",
                "bias_impact": "Mendukung Dolar AS / Menekan Emas jika klaim rendah",
                "impact_type": "sell",
                "importance": "Sedang (10% Bobot)"
            }
        ]

    elif "CPI" in mg or "INFLATION" in mg:
        return [
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

    elif "PPI" in mg:
        return [
            {
                "title": "Core PPI m/m (Inflasi Produsen Inti)",
                "category": "Inflasi Hulu",
                "status": "Indikator Biaya Produksi",
                "latest_data": "Komponen Input PCE",
                "relation_note": "Biaya produsen inti mengalir langsung ke perhitungan Core PCE (indikator inflasi favorit The Fed). Penurunan PPI membuka ruang pelonggaran moneter.",
                "bias_impact": "Dovish USD / Bullish XAU jika PPI melandai",
                "impact_type": "buy",
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
                "bias_impact": "Bullish XAU jika Yield turun pasca rilis",
                "impact_type": "buy",
                "importance": "Sedang (25% Bobot)"
            }
        ]

    elif "JOBLESS" in mg or "CLAIMS" in mg or "UNEMPLOYMENT" in mg or "JOLTS" in mg:
        return [
            {
                "title": "Initial Jobless Claims (Klaim Pengangguran Awal)",
                "category": "Pasar Tenaga Kerja",
                "status": "Rilis Mingguan Hari Kamis",
                "latest_data": "Indikator Kecepatan PHK",
                "relation_note": "Kenaikan klaim pengangguran di atas ekspektasi menandakan pelemahan pasar kerja AS, menekan DXY dan mendorong penguatan emas XAU/USD.",
                "bias_impact": "Dovish USD / Bullish XAU jika klaim > Forecast",
                "impact_type": "buy",
                "importance": "Sangat Tinggi (45% Bobot)"
            },
            {
                "title": "Continuing Jobless Claims (Klaim Berkelanjutan)",
                "category": "Durasi Pengangguran",
                "status": "Konfirmasi Tren Serapan Kerja",
                "latest_data": "Pantau Tren 4-Minggu",
                "relation_note": "Peningkatan klaim berkelanjutan menunjukkan pekerja yang terkena PHK semakin sulit mendapat pekerjaan baru, sinyal pendinginan ekonomi yang mendukung emas.",
                "bias_impact": "Bullish XAU jika tren klaim meningkat",
                "impact_type": "buy",
                "importance": "Tinggi (30% Bobot)"
            },
            {
                "title": "US 10Y Treasury Yield & Indeks Dolar (DXY)",
                "category": "Intermarket",
                "status": "Sensitivitas Suku Bunga",
                "latest_data": "Reaksi Instan Algoritma",
                "relation_note": "Data klaim yang lebih rendah dari konsensus memperkuat narasi pasar tenaga kerja ketat, menopang DXY dan menahan kenaikan emas.",
                "bias_impact": "Bearish XAU jika klaim < Forecast",
                "impact_type": "sell",
                "importance": "Sedang (25% Bobot)"
            }
        ]

    elif "FOMC" in mg or "FED" in mg or "PCE" in mg:
        return [
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
                "title": "Core PCE Price Index (Indikator Favorit The Fed)",
                "category": "Inflasi Konsumsi Pribadi",
                "status": "Target 2.0% The Fed",
                "latest_data": "Jangkar Proyeksi Moneter",
                "relation_note": "The Fed mendasarkan proyeksi kebijakan moneter jangka menengah pada angka PCE inti dibanding CPI umum.",
                "bias_impact": "Hawkish USD jika PCE bertahan di atas target",
                "impact_type": "sell",
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

    else:
        return [
            {
                "title": "Initial Jobless Claims (Klaim Pengangguran Mingguan)",
                "category": "Tenaga Kerja",
                "status": "Indikator Mingguan AS",
                "latest_data": "Pantau Tren Ketenagakerjaan",
                "relation_note": "Kondisi ketenagakerjaan yang kuat menghilangkan kekhawatiran resesi dari The Fed saat menentukan kebijakan moneter.",
                "bias_impact": "Hawkish USD / Bearish XAU jika klaim rendah",
                "impact_type": "sell",
                "importance": "Tinggi (35% Bobot)"
            },
            {
                "title": "ISM Manufacturing & Services PMI",
                "category": "Aktivitas Bisnis",
                "status": "Batas Ekspansi 50.0",
                "latest_data": "Barometer Siklus Ekonomi",
                "relation_note": "Aktivitas bisnis yang solid mendukung permintaan Dolar AS, sedangkan kontraksi di bawah 50 memicu permintaan safe-haven emas.",
                "bias_impact": "Mendukung Dolar AS jika di atas ekspektasi",
                "impact_type": "sell",
                "importance": "Sedang (35% Bobot)"
            },
            {
                "title": "US 10Y Treasury Yield & Dollar Index (DXY)",
                "category": "Pasar Modal & Valas",
                "status": "Imbal Hasil Obligasi",
                "latest_data": "Korelasi Intermarket",
                "relation_note": "Korelasi negatif kuat antara Dolar AS / Yield Treasury dan harga emas spot XAU/USD.",
                "bias_impact": "Bearish XAU saat DXY menguat",
                "impact_type": "sell",
                "importance": "Sedang (30% Bobot)"
            }
        ]
