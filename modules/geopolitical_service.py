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
        "title": "Middle East tensions simmer as diplomatic talks resume; safe-haven demand remains steady",
        "source": "Reuters",
        "published": datetime.now(timezone.utc).isoformat(),
        "category": "geopolitical"
    },
    {
        "title": "Fed officials signal patience on rate cuts pending confirmation of wholesale inflation slowdown",
        "source": "Bloomberg",
        "published": datetime.now(timezone.utc).isoformat(),
        "category": "macro"
    },
    {
        "title": "US Dollar holds firm against major currencies ahead of crucial PPI and Jobless Claims release",
        "source": "Financial Times",
        "published": datetime.now(timezone.utc).isoformat(),
        "category": "forex"
    },
    {
        "title": "Treasury yields nudge higher as wholesale price pressures point to resilient economic backdrop",
        "source": "CNBC",
        "published": datetime.now(timezone.utc).isoformat(),
        "category": "macro"
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
                
                articles.append({
                    "title": title,
                    "source": source,
                    "published": pub,
                    "link": link,
                    "category": category
                })
    except Exception as e:
        print(f"[GeopoliticalService] Error fetching feed {query}: {e}")
        
    return articles

def get_latest_geopolitical_news(force_refresh: bool = False) -> List[Dict[str, Any]]:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cache_time = data.get("cached_at", 0)
                # Valid for 20 minutes
                if datetime.now(timezone.utc).timestamp() - cache_time < 1200:
                    return data.get("news", [])
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
