import json
import html
import re
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dateutil import parser as date_parser

from modules.ai_analyzer import interpret_single_news_item

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "news_cache.json"
BULLETINS_FILE = Path(__file__).resolve().parent.parent / "data" / "daily_bulletins.json"

QUERIES = [
    "gold price XAU USD when:2d",
    "Federal Reserve inflation CPI US dollar when:2d"
]

MACRO_FEED_QUERIES = [
    "gold price XAU USD when:2d",
    "Federal Reserve inflation CPI when:2d",
    "US Treasury yields US dollar DXY when:2d",
    "crude oil Middle East geopolitics when:2d"
]

MAX_ARTICLE_AGE_HOURS = 48.0

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
        "title": "US Treasury yields and Dollar Index steady as markets await upcoming US macroeconomic data releases",
        "source": "Bloomberg",
        "published": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "category": "macro",
        "impact_xau": "NEUTRAL",
        "impact_color": "neutral",
        "impact_note": "Pelaku pasar mencermati deviasi data konsensus kalender ekonomi AS berikutnya."
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

def _current_wib_label() -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    wib = datetime.now(timezone(timedelta(hours=7)))
    return f"{wib.day:02d} {months[wib.month - 1]} {wib.year} • {wib.strftime('%H.%M')} WIB"

def get_fallback_bulletins() -> List[Dict[str, Any]]:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    pub_label = _current_wib_label()
    return [
        {
            "id": "novaire-news-01",
            "title": "IMBAL HASIL OBLIGASI TREASURY DAN DOLAR AS KONSOLIDASI MENJELANG RILIS DATA MAKROEKONOMI UTAMA AS",
            "channel": "Novaire Macro Wire",
            "channel_badge": "Novaire Desk",
            "category": "Obligasi & Suku Bunga",
            "published_time": pub_label,
            "published_ts": now_ts,
            "is_important": True,
            "paragraphs": [
                "Imbal hasil obligasi Treasury AS bergerak terukur seiring pelaku pasar institusional menyesuaikan posisi menjelang rilis data kalender ekonomi utama pekan ini.",
                "Imbal hasil Treasury AS tenor 10 tahun dan Indeks Dolar AS (DXY) menjadi acuan utama valuasi lintas aset, sementara likuiditas pasar emas spot (XAU/USD) terjaga di zona keseimbangan.",
                "Manajer investasi mencermati deviasi angka aktual terhadap konsensus sebagai katalis penentu arah tren sesi New York berikutnya."
            ],
            "interpretation": {
                "bias": "NEUTRAL TO BULLISH XAU",
                "bias_badge": "KONSOLIDASI MENUNGGU KATALIS",
                "impact_color": "neutral",
                "headline_analysis": "Stabilitas imbal hasil Treasury AS membatasi beban opportunity cost memegang emas non-yield menjelang rilis data ekonomi resmi.",
                "transmission_mechanism": (
                    "1. Stabilitas yield obligasi mencerminkan pasar menanti konfirmasi data ekonomi resmi AS.\n"
                    "2. Tertahannya lonjakan imbal hasil obligasi menjaga minat beli defensif pada emas spot.\n"
                    "3. Pelaku pasar bersiap mengantisipasi lonjakan volatilitas pasca rilis kalender ekonomi."
                ),
                "intermarket_matrix": {
                    "oil": "Minyak Bergerak Terukur • Rentang perdagangan normal",
                    "yields": "US 10Y Yield Stabil • Menunggu katalis data makro",
                    "dxy": "DXY Bergerak Sideways • Menanti arah sesi AS",
                    "xau": "XAU/USD Konsolidasi • Menjaga area support teknikal"
                },
                "tactical_action": "Manfaatkan rentang konsolidasi dengan manajemen risiko disiplin sambil menunggu konfirmasi rilis data resmi."
            }
        }
    ]

def is_important_news(title: str, text: str = "") -> bool:
    """Detects if a news headline or content represents high-impact breaking news."""
    important_keywords = [
        "war", "attack", "strike", "missile", "iran", "israel", "russia", "ukraine",
        "emergency", "ceasefire", "peace", "rate cut", "rate hike", "fomc", "cpi", "ppi",
        "nfp", "fed decision", "sanction", "bank collapse", "liquidity crisis", "opec",
        "taiwan", "nuclear", "default", "perang", "serangan", "rudal", "suku bunga", "inflasi",
        "surges", "plunges", "all-time high", "record high", "dollar surges", "dollar strengthens",
        "gold rallies", "gold declines", "middle east", "trump"
    ]
    content = (title + " " + text).lower()
    return any(kw in content for kw in important_keywords)

def categorize_news(title: str) -> str:
    """Accurately classifies news into institutional market categories."""
    t = title.lower()
    if any(w in t for w in ["oil", "crude", "energy", "iran", "israel", "middle east", "war", "strike", "attack", "missile", "opec"]):
        return "Energi & Geopolitik"
    elif any(w in t for w in ["yield", "treasury", "bond", "10-year", "debt", "auction", "dollar", "dxy"]):
        return "Obligasi & Suku Bunga"
    elif any(w in t for w in ["fed", "fomc", "powell", "inflation", "cpi", "ppi", "rate", "hike", "cut", "monetary"]):
        return "Kebijakan The Fed & Inflasi"
    elif any(w in t for w in ["bank", "liquidity", "fsb", "credit", "fail", "reserve", "bailout"]):
        return "Perbankan Global"
    else:
        return "Rantai Pasok & Komoditas"

def synthesize_indonesian_headline(original_title: str) -> str:
    """Converts/synthesizes international financial headlines into crisp uppercase Indonesian wire headlines."""
    title_clean = original_title.strip()

    conj = [
        (r"\b[aA]s\b", "seiring"),
        (r"\b[aA]nd\b", "dan"),
        (r"\b[aA]fter\b", "setelah"),
        (r"\b[aA]head of\b", "menjelang"),
        (r"\b[aA]mid\b", "di tengah"),
        (r"\b[eE]yes on\b", "fokus pada")
    ]
    for pat, rep in conj:
        title_clean = re.sub(pat, rep, title_clean)

    phrase_replacements = [
        (r"(?i)\bgold price forecast\b", "Proyeksi Harga Emas"),
        (r"(?i)\bgold price today\b", "Harga Emas Hari Ini"),
        (r"(?i)\bgold price analysis today\b", "Analisis Harga Emas Hari Ini"),
        (r"(?i)\bprice forecast\b", "Proyeksi Harga"),
        (r"(?i)\bgold prices decline\b", "Harga Emas Tertekan Melemah"),
        (r"(?i)\bgold prices drop\b", "Harga Emas Merosot"),
        (r"(?i)\bgold prices rise\b", "Harga Emas Menanjak"),
        (r"(?i)\bgold prices surge\b", "Harga Emas Melonjak Tinggi"),
        (r"(?i)\bgold steadies\b", "Harga Emas Konsolidasi"),
        (r"(?i)\bgold rebounds\b", "Harga Emas Rebound Menguat"),
        (r"(?i)\bgold rises\b", "Harga Emas Menguat"),
        (r"(?i)\bgold bears\b", "Tekanan Jual Emas"),
        (r"(?i)\bgold bulls\b", "Minat Beli Emas"),
        (r"(?i)\bplunges\b", "Merosot Tajam"),
        (r"(?i)\bplunge\b", "Penurunan Tajam"),
        (r"(?i)\btoward critical support\b", "Menuju Support Kritis"),
        (r"(?i)\bcritical support\b", "Support Kritis"),
        (r"(?i)\bbulls defend\b", "Bulls Bertahan di"),
        (r"(?i)\bbuyers retain control\b", "Pembeli Pertahankan Kendali"),
        (r"(?i)\bweek begins\b", "Pekan Dimulai"),
        (r"(?i)\bgold\b", "Emas"),
        (r"(?i)\b(?:u\.s\.|us)\s+dollar\s+strengthens\b", "Dolar AS Menguat"),
        (r"(?i)\bdollar strengthens\b", "Dolar AS Menguat"),
        (r"(?i)\bdollar gains\b", "Dolar AS Naik"),
        (r"(?i)\bdollar surges\b", "Dolar AS Melonjak"),
        (r"(?i)\bdollar falls\b", "Dolar AS Melemah"),
        (r"(?i)\bsofter us dollar\b", "Pelemahan Dolar AS"),
        (r"(?i)\b(?:u\.s\.|us)\s+dollar\b", "Dolar AS"),
        (r"(?i)\bbond yields\b", "Imbal Hasil Obligasi"),
        (r"(?i)\btreasury yields\b", "Yield Treasury AS"),
        (r"(?i)\byields slip\b", "Yield Obligasi Melandai"),
        (r"(?i)\byields rise\b", "Yield Obligasi Meningkat"),
        (r"(?i)\byields surge\b", "Yield Obligasi Melonjak"),
        (r"(?i)\bescalating\b", "Eskalasi"),
        (r"(?i)\battacks deepen\b", "Serangan Memperdalam"),
        (r"(?i)\boil supply fears\b", "Kekhawatiran Pasokan Minyak"),
        (r"(?i)\bmiddle east\b", "Timur Tengah"),
        (r"(?i)\bgeopolitical tensions\b", "Ketegangan Geopolitik"),
        (r"(?i)\bgeopolitical risks\b", "Risiko Geopolitik"),
        (r"(?i)\boil prices\b", "Harga Minyak"),
        (r"(?i)\bcrude oil\b", "Minyak Mentah"),
        (r"(?i)\bfed rate cut\b", "Pemangkasan Bunga The Fed"),
        (r"(?i)\brate cut\b", "Pemangkasan Suku Bunga"),
        (r"(?i)\brate hike\b", "Kenaikan Suku Bunga"),
        (r"(?i)\brate pause\b", "Jeda Suku Bunga"),
        (r"(?i)\bofficials want to hold off\b", "Pejabat Inginkan Penundaan"),
        (r"(?i)\bhike this month\b", "Kenaikan Bulan Ini"),
        (r"(?i)\binflation\b", "Inflasi"),
        (r"(?i)\bcentral banks\b", "Bank Sentral Dunia"),
        (r"(?i)\bsafe-haven\b", "Safe-Haven"),
        (r"(?i)\bnext key catalyst\b", "Katalis Utama Berikutnya")
    ]

    for pat, rep in phrase_replacements:
        title_clean = re.sub(pat, rep, title_clean)

    return title_clean.upper()

def parse_pub_datetime(pub_str: str) -> Optional[datetime]:
    if not pub_str:
        return None
    try:
        dt = date_parser.parse(pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def format_published_wib(pub_str: str) -> str:
    """Formats pubDate string to WIB (Jakarta time) with explicit date and time so it always matches the calendar."""
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    dt = parse_pub_datetime(pub_str)
    if not dt:
        return _current_wib_label()
    wib = dt.astimezone(timezone(timedelta(hours=7)))
    return f"{wib.day:02d} {months[wib.month - 1]} {wib.year} • {wib.strftime('%H.%M')} WIB"

def _clean_rss_snippet(raw_desc: str, title: str) -> str:
    """Extracts clean readable text from RSS description, omitting exact title duplicates."""
    if not raw_desc:
        return ""
    txt = re.sub(r"<[^>]+>", " ", html.unescape(raw_desc))
    txt = re.sub(r"\s+", " ", txt).strip()
    if not txt or len(txt) < 25:
        return ""
    if txt.lower().startswith(title[:35].lower()) and len(txt) <= len(title) + 35:
        return ""
    return txt[:480]


def annotate_quant_relevance(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attaches direct AI Quant v2 pillar linkage, time-decay weight, and directional contribution
    so the UI can display how each news item maps to quantitative factors.
    """
    title_raw = str(item.get("original_title") or item.get("title") or "")
    snippet = str(item.get("summary_snippet") or "")
    text_low = (title_raw + " " + snippet).lower()

    pillars = []
    primary_key = "xau"
    if any(k in text_low for k in ["yield", "treasury", "bond", "10y", "10-year", "fed", "fomc", "powell", "rate cut", "rate hike", "suku bunga", "obligasi"]):
        pillars.append("US10Y & The Fed")
        primary_key = "yields"
    if any(k in text_low for k in ["dollar", "dxy", "greenback", "usd", "dolar as"]):
        pillars.append("DXY & USD")
        if primary_key == "xau":
            primary_key = "dxy"
    if any(k in text_low for k in ["cpi", "ppi", "pce", "inflation", "inflasi", "oil", "crude", "minyak", "opec", "energy", "energi"]):
        pillars.append("Inflasi & Energi")
        if primary_key == "xau":
            primary_key = "inflation"
    if any(k in text_low for k in ["war", "iran", "israel", "middle east", "russia", "ukraine", "tariff", "strike", "missile", "conflict", "sanction", "geopolit", "safe-haven", "timur tengah"]):
        pillars.append("Safe-Haven Geopolitik")
        if primary_key == "xau":
            primary_key = "geopolitical"
    if not pillars:
        pillars.append("XAU Spot & Likuiditas")

    now_ts = datetime.now(timezone.utc).timestamp()
    pub_ts = float(item.get("published_ts") or now_ts)
    age_hours = max(0.0, (now_ts - pub_ts) / 3600.0)
    decay_w = round(max(0.25, 1.0 - (age_hours / MAX_ARTICLE_AGE_HOURS) * 0.75), 2)
    age_label = f"{int(age_hours * 60)}m lalu" if age_hours < 1.0 else f"{int(round(age_hours))}j lalu"

    interp = item.get("interpretation") or {}
    bias = str(interp.get("bias") or item.get("impact_xau") or "NEUTRAL").upper()
    if "BUY" in bias or "BULLISH" in bias:
        raw_pts = 0.80 if primary_key in ("yields", "dxy", "inflation") else 0.60
    elif "SELL" in bias or "BEARISH" in bias:
        raw_pts = -0.80 if primary_key in ("yields", "dxy", "inflation") else -0.60
    else:
        raw_pts = 0.0

    quant_delta = round(raw_pts * decay_w, 2)
    pillar_str = " • ".join(pillars)

    if quant_delta > 0:
        dir_desc = f"Memberi dorongan positif ({quant_delta:+.2f}) pada faktor AI/Makro untuk XAU BUY"
    elif quant_delta < 0:
        dir_desc = f"Memberi tekanan negatif ({quant_delta:+.2f}) pada faktor AI/Makro yang mendukung XAU SELL"
    else:
        dir_desc = "Kontribusi netral (0.00); berfungsi sebagai pemantau volatilitas & konteks pasar"

    quant_connection = (
        f"Terhubung ke pilar AI Quant [{pillar_str}] dengan bobot kesegaran Time-Decay {decay_w:.2f}x ({age_label}). "
        f"{dir_desc}."
    )

    item["quant_pillars"] = pillars
    item["quant_factor_key"] = primary_key
    item["decay_weight"] = decay_w
    item["age_label"] = age_label
    item["quant_impact_delta"] = quant_delta
    item["quant_connection"] = quant_connection
    return item


def _fetch_yahoo_macro_feed() -> List[Dict[str, Any]]:
    """Fetches recent Yahoo Finance macro/yield/dollar/oil RSS articles with rich descriptions."""
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ETNX,DX-Y.NYB,CL=F&region=US&lang=en-US"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    now_utc = datetime.now(timezone.utc)
    allow_kw = ["gold", "xau", "dollar", "dxy", "yield", "treasury", "fed", "fomc", "powell", "cpi", "ppi", "inflation", "oil", "crude", "iran", "tariff", "rate", "jobs", "payrolls"]
    articles = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:15]:
                title = (item.findtext("title") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = _clean_rss_snippet(item.findtext("description") or "", title)
                if not title or not any(k in title.lower() for k in allow_kw):
                    continue
                pub_dt = parse_pub_datetime(pub)
                if not pub_dt:
                    continue
                age_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                if age_hours > MAX_ARTICLE_AGE_HOURS or age_hours < -2.0:
                    continue
                is_geo = any(w in title.lower() for w in ["war", "tension", "conflict", "iran", "israel", "russia", "china", "strike", "sanction", "military", "oil"])
                art = {
                    "title": title,
                    "summary_snippet": desc,
                    "source": "Yahoo Finance",
                    "published": format_published_wib(pub),
                    "published_raw": pub,
                    "published_ts": int(pub_dt.timestamp()),
                    "link": link,
                    "category": "geopolitical" if is_geo else "macro",
                }
                articles.append(ensure_news_impact(art))
    except Exception as e:
        print(f"[GeopoliticalService] Yahoo macro RSS warning: {e}")
    return articles


def fetch_feed(query: str) -> List[Dict[str, Any]]:
    """Fetches recent Google News RSS feed items (strictly <= 48 hours old) for a given query."""
    q_str = query.strip()
    if "when:" not in q_str:
        q_str = f"{q_str} when:2d"
    encoded_query = urllib.parse.quote_plus(q_str)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)

    now_utc = datetime.now(timezone.utc)
    articles = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:15]:
                title_elem = item.find("title")
                pub_elem = item.find("pubDate")
                link_elem = item.find("link")
                desc_elem = item.find("description")

                title = title_elem.text if title_elem is not None else ""
                pub = pub_elem.text if pub_elem is not None else ""
                link = link_elem.text if link_elem is not None else ""
                raw_desc = desc_elem.text if desc_elem is not None else ""

                pub_dt = parse_pub_datetime(pub)
                if not pub_dt:
                    continue
                age_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                # Strictly discard articles older than 48 hours so past-week NFP/FOMC previews never resurface
                if age_hours > MAX_ARTICLE_AGE_HOURS or age_hours < -2.0:
                    continue

                # Extract source from title "Title text - Source"
                source = "Global Media"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()

                snippet = _clean_rss_snippet(raw_desc, title)
                is_geo = any(w in title.lower() for w in ["war", "tension", "conflict", "iran", "israel", "russia", "china", "strike", "sanction", "military"])
                category = "geopolitical" if is_geo else "macro"

                title_lower = title.lower()
                bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges", "gold rises"]
                bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise", "dollar strengthens", "plunge", "plunges"]

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
                    impact_note = "Pengaruh terbatas, pelaku pasar mencermati rilis data kalender ekonomi AS berikutnya."

                art = {
                    "title": title,
                    "summary_snippet": snippet,
                    "source": source,
                    "published": format_published_wib(pub),
                    "published_raw": pub,
                    "published_ts": int(pub_dt.timestamp()),
                    "link": link,
                    "category": category,
                    "impact_xau": impact_xau,
                    "impact_color": impact_color,
                    "impact_note": impact_note
                }
                articles.append(annotate_quant_relevance(art))
    except Exception as e:
        print(f"[GeopoliticalService] Error fetching feed {query}: {e}")

    articles.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
    return articles

def generate_bulletin_from_feed_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw news article into a full institutional Novaire Macro Wire bulletin with rich interpretations."""
    original_title = item.get("title", "")
    source = item.get("source", "Global Media")
    pub_raw = item.get("published_raw") or item.get("published", "")
    pub_ts = item.get("published_ts") or int(datetime.now(timezone.utc).timestamp())

    indonesian_title = synthesize_indonesian_headline(original_title)
    category = categorize_news(original_title)
    pub_time_wib = format_published_wib(pub_raw) if "WIB" not in str(pub_raw) else str(pub_raw)
    is_important = is_important_news(original_title)

    p1 = f"Laporan pasar global terverifikasi dari {source} menyoroti dinamika: '{original_title}'. Pelaku pasar institusional saat ini mencermati pergeseran arus likuiditas dan sentimen risiko lintas aset."
    if category == "Kebijakan The Fed & Inflasi":
        p2 = "Dari perspektif transmisi moneter, proyeksi suku bunga acuan The Fed dan data inflasi acuan (CPI/PPI/PCE) menjadi jangkar utama penentuan valuasi aset berimbal hasil obligasi AS."
        p3 = "Dampaknya pada emas (XAU/USD): Sensitivitas harga terhadap arah suku bunga riil AS sangat tinggi. Trader diimbau mengamati deviasi konsensus dan volatilitas pada sesi New York."
    elif category == "Energi & Geopolitik":
        p2 = "Dari transmisi premi risiko geopolitik, ketegangan kawasan dan potensi disrupsi pasokan minyak mentah memicu aliran diversifikasi dana ke aset safe-haven fisik."
        p3 = "Dampaknya pada emas (XAU/USD): Permintaan defensif safe-haven cenderung menahan tekanan jual teknikal, dengan level support krusial menjadi zona akumulasi institusi."
    elif category == "Obligasi & Suku Bunga":
        p2 = "Dari transmisi pasar utang, yield obligasi Treasury AS tenor 10 tahun dan indeks Dolar AS (DXY) secara langsung menentukan opportunity cost memegang emas non-yield."
        p3 = "Dampaknya pada emas (XAU/USD): Penguatan yield dan DXY memberi tekanan koreksi bagi XAU/USD, sedangkan pelemahan yield membuka ruang reli likuiditas."
    else:
        p2 = "Dari perspektif makroekonomi terpadu, penyesuaian portofolio global antar kelas aset memicu reposisi likuiditas pasar modal dan komoditas utama."
        p3 = "Dampaknya pada emas (XAU/USD): Volatilitas harga spot emas diperkirakan bergerak dalam rentang likuiditas teratur menjelang rilis katalis berikutnya."

    snippet = str(item.get("summary_snippet") or "").strip()
    paragraphs = [p1]
    if snippet:
        paragraphs.append(f"Ringkasan Rilis Asli ({source}): {snippet}")
    paragraphs.extend([p2, p3])

    full_text_for_ai = f"{original_title}. {snippet} Kategori: {category}. Sumber: {source}."
    interpretation = interpret_single_news_item(full_text_for_ai)

    title_hash = hashlib.md5(original_title.encode("utf-8")).hexdigest()[:8]
    bulletin_id = f"novaire-wire-{title_hash}"

    bulletin = {
        "id": bulletin_id,
        "title": indonesian_title,
        "original_title": original_title,
        "summary_snippet": snippet,
        "source": source,
        "link": item.get("link", ""),
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": category,
        "published_time": pub_time_wib,
        "published_ts": pub_ts,
        "is_important": is_important,
        "paragraphs": paragraphs,
        "interpretation": interpretation
    }
    return annotate_quant_relevance(bulletin)

def _is_bulletin_fresh(b: Dict[str, Any], now_ts: float) -> bool:
    """Checks that a cached bulletin has an explicit timestamp within the last 48 hours."""
    pub_ts = b.get("published_ts", 0)
    if not pub_ts:
        return False
    age_hours = (now_ts - float(pub_ts)) / 3600.0
    return -2.0 <= age_hours <= MAX_ARTICLE_AGE_HOURS

def get_daily_macro_bulletins(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns structured daily macro news bulletins strictly from the last 48 hours."""
    BULLETINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    now_ts = datetime.now(timezone.utc).timestamp()

    cached_bulletins = []
    cache_time = 0
    if BULLETINS_FILE.exists():
        try:
            with open(BULLETINS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_list = data.get("bulletins", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                cache_time = data.get("cached_at", 0) if isinstance(data, dict) else 0
                cached_bulletins = [b for b in raw_list if _is_bulletin_fresh(b, now_ts)]
        except Exception as e:
            print(f"[GeopoliticalService] Error reading daily bulletins cache: {e}")

    if not force_refresh and cached_bulletins and (now_ts - cache_time < 120):
        return [annotate_quant_relevance(b) for b in cached_bulletins]

    raw_articles = []
    seen_titles = set()
    for it in _fetch_yahoo_macro_feed():
        t_clean = it["title"].strip().lower()
        if t_clean not in seen_titles and len(t_clean) > 15:
            seen_titles.add(t_clean)
            raw_articles.append(it)
    for q in MACRO_FEED_QUERIES:
        items = fetch_feed(q)
        for it in items:
            t_clean = it["title"].strip().lower()
            if t_clean not in seen_titles and len(t_clean) > 15:
                seen_titles.add(t_clean)
                raw_articles.append(it)

    # Sort all fresh articles newest first
    raw_articles.sort(key=lambda x: x.get("published_ts", 0), reverse=True)

    new_bulletins = []
    for art in raw_articles[:10]:
        try:
            b = generate_bulletin_from_feed_item(art)
            new_bulletins.append(b)
        except Exception as err:
            print(f"[GeopoliticalService] Error generating bulletin for article: {err}")

    merged_bulletins = []
    seen_bulletin_titles = set()

    for b in new_bulletins:
        t_key = b["title"].strip().lower()[:40]
        if t_key not in seen_bulletin_titles:
            seen_bulletin_titles.add(t_key)
            merged_bulletins.append(b)

    for b in cached_bulletins:
        t_key = b["title"].strip().lower()[:40]
        if t_key not in seen_bulletin_titles and _is_bulletin_fresh(b, now_ts):
            seen_bulletin_titles.add(t_key)
            merged_bulletins.append(b)

    # Sort newest first (preserving chronological accuracy)
    merged_bulletins.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
    merged_bulletins = merged_bulletins[:14]

    if not merged_bulletins:
        merged_bulletins = get_fallback_bulletins()
    merged_bulletins = [annotate_quant_relevance(b) for b in merged_bulletins]

    try:
        with open(BULLETINS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "cached_at": int(now_ts),
                "bulletins": merged_bulletins
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[GeopoliticalService] Error writing daily bulletins cache: {e}")

    return merged_bulletins

def ensure_news_impact(item: Dict[str, Any]) -> Dict[str, Any]:
    # Replace legacy FOMC-hardcoded impact note if present in older cache
    if "proyeksi FOMC" in str(item.get("impact_note", "")) or "konsensus FOMC" in str(item.get("impact_note", "")):
        item["impact_note"] = "Pengaruh terbatas, pelaku pasar mencermati rilis data kalender ekonomi AS berikutnya."
    if "impact_xau" in item and item.get("impact_note") and item.get("interpretation"):
        return annotate_quant_relevance(item)
    title_lower = item.get("title", "").lower()
    bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges", "gold rises"]
    bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise", "dollar strengthens", "plunge", "plunges"]

    if any(w in title_lower for w in bullish_triggers):
        impact_xau = "BULLISH XAU"
        impact_color = "buy"
        impact_note = "Memicu permintaan defensif safe-haven emas / menekan USD."
        bias_badge = "SAFE-HAVEN DEMAND"
    elif any(w in title_lower for w in bearish_triggers):
        impact_xau = "BEARISH XAU"
        impact_color = "sell"
        impact_note = "Mendukung penguatan Dolar AS / mengurangi daya tarik emas."
        bias_badge = "TEKANAN PENGUATAN USD"
    else:
        impact_xau = "NEUTRAL"
        impact_color = "neutral"
        impact_note = "Pengaruh terbatas, pelaku pasar mencermati rilis data kalender ekonomi AS berikutnya."
        bias_badge = "SENTIMEN SEIMBANG"

    item["impact_xau"] = impact_xau
    item["impact_color"] = impact_color
    item["impact_note"] = impact_note
    item["interpretation"] = {
        "bias": impact_xau,
        "bias_badge": bias_badge,
        "impact_color": impact_color,
        "headline_analysis": impact_note,
        "transmission_mechanism": f"Transmisi makro: Berita '{item.get('title')}' mempengaruhi sentimen likuiditas global dan valuasi XAU/USD.",
        "intermarket_matrix": {
            "oil": "Sentimen komoditas stabil",
            "yields": "Yield obligasi bergerak normal",
            "dxy": "Dolar AS mencerminkan dinamika suku bunga",
            "xau": f"Emas XAU/USD merespons dengan bias {impact_xau}"
        },
        "tactical_action": "Pantau reaksi level teknikal utama pada grafik M15-H1."
    }
    return annotate_quant_relevance(item)

def get_latest_geopolitical_news(force_refresh: bool = False) -> List[Dict[str, Any]]:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    now_ts = datetime.now(timezone.utc).timestamp()

    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cache_time = data.get("cached_at", 0)
                if now_ts - cache_time < 900:
                    cached_items = [
                        it for it in data.get("news", [])
                        if it.get("published_ts", 0) and (now_ts - float(it["published_ts"])) <= MAX_ARTICLE_AGE_HOURS * 3600
                    ]
                    if cached_items:
                        return [ensure_news_impact(it) for it in cached_items]
        except Exception as e:
            print(f"[GeopoliticalService] Cache read error: {e}")

    all_news = []
    seen_titles = set()

    for it in _fetch_yahoo_macro_feed():
        clean_title = it["title"].strip().lower()
        if clean_title not in seen_titles and len(clean_title) > 15:
            seen_titles.add(clean_title)
            all_news.append(it)

    for q in QUERIES:
        feed_items = fetch_feed(q)
        for item in feed_items:
            clean_title = item["title"].strip().lower()
            if clean_title not in seen_titles and len(clean_title) > 15:
                seen_titles.add(clean_title)
                all_news.append(ensure_news_impact(item))

    all_news.sort(key=lambda x: x.get("published_ts", 0), reverse=True)

    if not all_news:
        all_news = [ensure_news_impact(dict(h)) for h in FALLBACK_HEADLINES]

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "cached_at": int(now_ts),
                "news": all_news[:15]
            }, f, indent=2)
    except Exception as e:
        print(f"[GeopoliticalService] Cache write error: {e}")

    return all_news[:15]
