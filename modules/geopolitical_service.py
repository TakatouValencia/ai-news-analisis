import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "news_cache.json"

QUERIES = [
    "gold+geopolitical+OR+middle+east+OR+tensions+when:3d",
    "fed+inflation+OR+fomc+OR+cpi+ppi+when:3d"
]

FALLBACK_HEADLINES = [
    {
        "title": "Middle East naval security alert raised amid maritime standoff; safe-haven demand caps gold downside",
        "source": "Reuters",
        "published": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "category": "geopolitical",
        "impact_xau": "BULLISH XAU",
        "impact_color": "buy",
        "impact_note": "Ketegangan rute maritim memicu pembelian defensif emas safe-haven."
    },
    {
        "title": "Fed Governor Bowman confirms appetite for rate increase if inflation indicators stay sticky above target",
        "source": "Bloomberg",
        "published": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "category": "macro",
        "impact_xau": "BEARISH XAU",
        "impact_color": "sell",
        "impact_note": "Pernyataan hawkish pejabat The Fed memperkuat ekspektasi target rate 3.75 - 4.00%."
    },
    {
        "title": "US Dollar Index firms above 104.5 as markets price in 83% probability of Fed tightening",
        "source": "Financial Times",
        "published": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "category": "forex",
        "impact_xau": "BEARISH XAU",
        "impact_color": "sell",
        "impact_note": "Kekuatan Dolar AS secara langsung menekan valuasi emas spot XAU/USD."
    },
    {
        "title": "Global Central Banks continue reserve diversification with net monthly gold purchases",
        "source": "World Gold Council",
        "published": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "category": "geopolitical",
        "impact_xau": "BULLISH XAU",
        "impact_color": "buy",
        "impact_note": "Akumulasi bank sentral global memberikan bantalan support fundamental jangka panjang."
    }
]

def fetch_feed(query: str) -> List[Dict[str, Any]]:
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    
    articles = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:10]:
                title_elem = item.find("title")
                pub_elem = item.find("pubDate")
                link_elem = item.find("link")
                
                title = title_elem.text if title_elem is not None else ""
                pub = pub_elem.text if pub_elem is not None else ""
                link = link_elem.text if link_elem is not None else ""
                
                # Extract source from title "Title text - Source"
                source = "Global Media"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                    
                is_geo = any(w in title.lower() for w in ["war", "tension", "conflict", "iran", "israel", "russia", "china", "strike", "sanction", "military"])
                category = "geopolitical" if is_geo else "macro"
                
                # Assess impact on Gold (XAU)
                title_lower = title.lower()
                bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges"]
                bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise"]
                
                if any(w in title_lower for w in bullish_triggers):
                    impact_xau = "BULLISH XAU"
                    impact_color = "buy"
                    impact_note = "Memicu permintaan safe-haven emas / menekan USD."
                elif any(w in title_lower for w in bearish_triggers):
                    impact_xau = "BEARISH XAU"
                    impact_color = "sell"
                    impact_note = "Mendukung Dolar AS / mengurangi daya tarik emas."
                else:
                    impact_xau = "NEUTRAL"
                    impact_color = "neutral"
                    impact_note = "Pengaruh terbatas, pasar fokus pada konsensus FOMC."
                
                articles.append({
                    "title": title,
                    "source": source,
                    "published": pub,
                    "link": link,
                    "category": category,
                    "impact_xau": impact_xau,
                    "impact_color": impact_color,
                    "impact_note": impact_note
                })
    except Exception as e:
        print(f"[GeopoliticalService] Error fetching feed {query}: {e}")
        
    return articles

def ensure_news_impact(item: Dict[str, Any]) -> Dict[str, Any]:
    if "impact_xau" in item and item.get("impact_note"):
        return item
    title_lower = item.get("title", "").lower()
    bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges"]
    bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise"]
    if any(w in title_lower for w in bullish_triggers):
        item["impact_xau"] = "BULLISH XAU"
        item["impact_color"] = "buy"
        item["impact_note"] = "Memicu permintaan defensif safe-haven emas / menekan USD."
    elif any(w in title_lower for w in bearish_triggers):
        item["impact_xau"] = "BEARISH XAU"
        item["impact_color"] = "sell"
        item["impact_note"] = "Mendukung penguatan Dolar AS / mengurangi daya tarik emas."
    else:
        item["impact_xau"] = "NEUTRAL"
        item["impact_color"] = "neutral"
        item["impact_note"] = "Pengaruh terbatas, volatilitas pasar terkonsentrasi pada proyeksi FOMC."
    return item

def get_latest_geopolitical_news(force_refresh: bool = False) -> List[Dict[str, Any]]:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cache_time = data.get("cached_at", 0)
                # Valid for 20 minutes
                if datetime.now(timezone.utc).timestamp() - cache_time < 1200:
                    cached_items = data.get("news", [])
                    return [ensure_news_impact(it) for it in cached_items]
        except Exception as e:
            print(f"[GeopoliticalService] Cache read error: {e}")
            
    all_news = []
    seen_titles = set()
    
    for q in QUERIES:
        feed_items = fetch_feed(q)
        for item in feed_items:
            clean_title = item["title"].strip().lower()
            if clean_title not in seen_titles and len(clean_title) > 15:
                seen_titles.add(clean_title)
                all_news.append(item)
                
    if not all_news:
        all_news = FALLBACK_HEADLINES
        
    # Cache results
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "cached_at": int(datetime.now(timezone.utc).timestamp()),
                "news": all_news[:15]
            }, f, indent=2)
    except Exception as e:
        print(f"[GeopoliticalService] Cache write error: {e}")
        
    return all_news[:15]
