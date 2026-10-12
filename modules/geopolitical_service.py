import json
import re
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any
from dateutil import parser as date_parser

from modules.ai_analyzer import interpret_single_news_item

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "news_cache.json"
BULLETINS_FILE = Path(__file__).resolve().parent.parent / "data" / "daily_bulletins.json"

QUERIES = [
    "gold price XAU USD",
    "Federal Reserve interest rate inflation CPI"
]

MACRO_FEED_QUERIES = [
    "gold price XAU USD",
    "Federal Reserve interest rate inflation CPI",
    "US Treasury yields US dollar DXY",
    "crude oil Middle East geopolitics"
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

FALLBACK_BULLETINS: List[Dict[str, Any]] = [
    {
        "id": "novaire-news-01",
        "title": "HARGA MINYAK TURUN SETELAH PERNYATAAN TRUMP MENGENAI PERUNDINGAN IRAN MEREDAKAN KEKHAWATIRAN PASOKAN",
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": "Energi & Geopolitik",
        "published_time": "18.54 WIB",
        "is_important": True,
        "paragraphs": [
            "Harga minyak turun pada Jumat setelah kekhawatiran mengenai pasokan dari Timur Tengah mereda. Presiden AS Donald Trump mengatakan bahwa AS tidak akan menyerang Iran sebelum pemilu AS bulan depan, di tengah perundingan produktif untuk mengakhiri perang yang telah mengganggu pasar energi global.",
            "Financial Stability Board, lembaga global yang memantau risiko sistem keuangan, mendesak pihak berwenang untuk memperkuat mekanisme pendanaan darurat bagi bank yang mengalami kegagalan likuiditas di tengah fluktuasi pasar.",
            "Pengetatan pengawasan pajak dan perlambatan belanja konsumen di AS menjadi sorotan terbaru bagi para manajer investasi global dalam mengukur daya beli dan arah inflasi."
        ],
        "interpretation": {
            "bias": "BEARISH XAU",
            "bias_badge": "RETRACEMENT TEKANAN JUAL",
            "impact_color": "sell",
            "headline_analysis": "Retorika diplomatis Trump memangkas premi risiko geopolitik minyak mentah, meredakan ketakutan pasar dan memicu aksi profit taking pada instrumen safe-haven emas.",
            "transmission_mechanism": (
                "1. Pelemahan harga minyak mentah secara langsung menekan ekspektasi lonjakan inflasi jangka pendek.\n"
                "2. Berkurangnya kepanikan konflik di Timur Tengah mengurangi aliran dana darurat (defensive flight-to-safety) ke emas spot.\n"
                "3. Emas (XAU/USD) rentan mengalami aksi ambil untung (profit taking) menguji area support demand kunci."
            ),
            "intermarket_matrix": {
                "oil": "WTI Minyak Melemah (-2.6%) • Tekanan premi risiko mereda",
                "yields": "US 10Y Yield 4.15% • Pergerakan tenang tanpa gejolak inflasi",
                "dxy": "Indeks Dolar (DXY) 104.20 • Menguat tipis merespons sentimen risk-on",
                "xau": "XAU/USD Koreksi Intraday • Uji support teknikal $2,630 - $2,645"
            },
            "tactical_action": "Hindari mengejar posisi Buy di dekat level resisten tinggi. Ambil sikap sabar (wait and see) untuk mengamati reaksi harga di area demand bawah sebelum entri kembali."
        }
    },
    {
        "id": "novaire-news-02",
        "title": "IMBAL HASIL OBLIGASI TREASURY STABIL SETELAH TRUMP MENUNJUKKAN SIKAP DIPLOMATIS TERHADAP IRAN MENJELANG PEMILU PARUH WAKTU",
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": "Obligasi & Suku Bunga",
        "published_time": "19.10 WIB",
        "is_important": False,
        "paragraphs": [
            "Imbal hasil obligasi sebagian besar stabil ketika investor mencermati hasil lelang Treasury terbaru dan janji Presiden Donald Trump untuk tidak menyerang Iran hingga pemilu selesai.",
            "Imbal hasil Treasury AS tenor 10 tahun, yang menjadi acuan utama untuk valuasi aset global, bergerak tenang di kisaran 4.14% - 4.18% seiring pasar menantikan kepastian data tenaga kerja resmi dan arah kebijakan suku bunga The Fed berikutnya."
        ],
        "interpretation": {
            "bias": "NEUTRAL TO BULLISH XAU",
            "bias_badge": "KONSOLIDASI MENUNGGU KATALIS",
            "impact_color": "neutral",
            "headline_analysis": "Imbal hasil Treasury 10Y AS yang terkunci di kisaran 4.15% membatasi beban opportunity cost memegang emas non-yield, menjaga XAU/USD dalam koridor konsolidasi sehat.",
            "transmission_mechanism": (
                "1. Stabilitas yield obligasi mencerminkan pasar telah menyerap isu politik tanpa memicu kenaikan ekspektasi yield baru.\n"
                "2. Dengan tertahannya yield obligasi di bawah resisten 4.22%, tekanan jual pada emas tidak meluas secara agresif.\n"
                "3. Pelaku pasar bersiap melakukan akumulasi bertahap di zona support mengantisipasi volatilitas rilis data resmi."
            ),
            "intermarket_matrix": {
                "oil": "Minyak Flat • Rentang perdagangan terukur",
                "yields": "US 10Y Yield 4.15% • Terjaga di batas ekuilibrium",
                "dxy": "DXY 104.15 • Bergerak sideways",
                "xau": "XAU/USD Range Bound • Menjaga pola swing higher low"
            },
            "tactical_action": "Manfaatkan rentang konsolidasi untuk scalping/swing intraday (Buy di area support, Take Profit di batas resisten) dengan manajemen risiko terukur."
        }
    },
    {
        "id": "novaire-news-03",
        "title": "FINANCIAL STABILITY BOARD (FSB) DESAK REFORMASI LIKUIDITAS DARURAT PERBANKAN LINTAS NEGARA",
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": "Perbankan Global",
        "published_time": "16.30 WIB",
        "is_important": True,
        "paragraphs": [
            "Financial Stability Board (FSB), badan pengawas sistem keuangan global, secara terbuka memperingatkan bahwa kesenjangan kapasitas likuiditas darurat antar-negara dapat mempercepat penyebaran penularan krisis finansial pada bank-bank bermasalah.",
            "Lembaga tersebut mendesak otoritas moneter negara-negara G20 untuk menyiapkan mekanisme pendanaan cepat bagi perbankan di tengah risiko suku bunga tinggi yang berkepanjangan dan volatilitas pasar obligasi."
        ],
        "interpretation": {
            "bias": "BULLISH XAU",
            "bias_badge": "LINDUNG NILAI RISIKO SISTEMIK",
            "impact_color": "buy",
            "headline_analysis": "Peringatan likuiditas perbankan dari lembaga global memperkuat daya tarik emas fisik sebagai instrumen lindung nilai risiko gagal bayar pihak ketiga.",
            "transmission_mechanism": (
                "1. Kekhawatiran likuiditas perbankan mendorong diversifikasi institusional dari instrumen utang komersial ke safe asset.\n"
                "2. Emas batangan tidak memiliki risiko pihak ketiga (zero counterparty risk) sehingga menjadi pilihan utama saat stabilitas perbankan disorot.\n"
                "3. Penurunan harga emas saat sesi reguler cenderung direspons aksi borong (buying the dip) oleh manajer investasi."
            ),
            "intermarket_matrix": {
                "oil": "Minyak Netral • Tidak terdampak langsung",
                "yields": "Yield Obligasi Tertekan • Pembelian surat utang jangka pendek",
                "dxy": "Dolar AS Bertahan sebagai Mata Uang Likuid",
                "xau": "XAU/USD Ditopang Akumulasi Pembeli Institusional"
            },
            "tactical_action": "Cari peluang Buy saat harga menguji area support dinamis. Tren fundamental jangka panjang tetap terjaga dalam jalur ekspansi."
        }
    },
    {
        "id": "novaire-news-04",
        "title": "KOMISI EROPA PERCEPAT 46 PROYEK KRUSIAL MINERAL STRATEGIS GUNA REDUKSI KETERGANTUNGAN PADA CHINA",
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": "Rantai Pasok & Komoditas",
        "published_time": "14.15 WIB",
        "is_important": False,
        "paragraphs": [
            "Komisi Eropa mengumumkan percepatan jalur perizinan dan dukungan pendanaan bagi 46 proyek bahan baku strategis seperti litium, kobalt, dan logam tanah jarang yang krusial untuk pertahanan, energi terbarukan, dan industri chip.",
            "Inisiatif ini diambil di tengah upaya blok Barat mengurangi dominasi China dalam rantai pasokan global, yang menandai fase baru fragmentasi perdagangan dunia dan polarisasi cadangan devisa."
        ],
        "interpretation": {
            "bias": "BULLISH XAU (JANGKA PANJANG)",
            "bias_badge": "DEDOLARISASI & FRAGMENTASI",
            "impact_color": "buy",
            "headline_analysis": "Fragmentasi rantai pasokan dan kompetisi sumber daya strategis mempercepat tren diversifikasi cadangan devisa bank sentral dunia menuju emas.",
            "transmission_mechanism": (
                "1. Ketegangan ekonomi antara Barat dan China mendorong bank-bank sentral negara berkembang mengurangi ketergantungan pada aset berbasis Dolar AS.\n"
                "2. Porsi cadangan emas batangan fisik terus ditingkatkan sebagai aset cadangan yang kebal terhadap sanksi dan intervensi geopolitik.\n"
                "3. Memberikan landasan support fundamental jangka panjang yang sangat kuat bagi harga emas dunia."
            ),
            "intermarket_matrix": {
                "oil": "Komoditas Tambang Menguat",
                "yields": "Yield Obligasi Bergerak Fluktuatif",
                "dxy": "Dolar AS Menghadapi Polarisasi Cadangan Devisa",
                "xau": "XAU/USD Mendapat Sentimen Positif Struktural"
            },
            "tactical_action": "Pertahankan perspektif bullish struktural untuk horizon swing dan posisi jangka menengah; beli di area koreksi teknikal signifikan."
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
    
    # 1. Conjunctions first to prevent replacing 'AS' in 'Dolar AS'
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
        
    # 2. Financial phrase replacements
    phrase_replacements = [
        (r"(?i)\bgold price forecast\b", "Proyeksi Harga Emas"),
        (r"(?i)\bgold price today\b", "Harga Emas Hari Ini"),
        (r"(?i)\bprice forecast\b", "Proyeksi Harga"),
        (r"(?i)\bgold prices decline\b", "Harga Emas Tertekan Melemah"),
        (r"(?i)\bgold prices drop\b", "Harga Emas Merosot"),
        (r"(?i)\bgold prices rise\b", "Harga Emas Menanjak"),
        (r"(?i)\bgold prices surge\b", "Harga Emas Melonjak Tinggi"),
        (r"(?i)\bgold steadies\b", "Harga Emas Konsolidasi"),
        (r"(?i)\bgold rebounds\b", "Harga Emas Rebound Menguat"),
        (r"(?i)\bgold bears\b", "Tekanan Jual Emas"),
        (r"(?i)\bgold bulls\b", "Minat Beli Emas"),
        (r"(?i)\bplunges\b", "Merosot Tajam"),
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

def format_published_wib(pub_str: str) -> str:
    """Formats pubDate string to WIB (Jakarta time)."""
    now_wib = datetime.now(timezone(timedelta(hours=7)))
    if not pub_str:
        return now_wib.strftime("%H.%M WIB")
    try:
        dt = date_parser.parse(pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        wib = dt.astimezone(timezone(timedelta(hours=7)))
        return wib.strftime("%H.%M WIB")
    except Exception:
        return now_wib.strftime("%H.%M WIB")

def fetch_feed(query: str) -> List[Dict[str, Any]]:
    """Fetches Google News RSS feed for a given query."""
    encoded_query = urllib.parse.quote_plus(query.strip())
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
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
                bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise", "dollar strengthens"]
                
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

def generate_bulletin_from_feed_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw news article into a full institutional Novaire Macro Wire bulletin with rich interpretations."""
    original_title = item.get("title", "")
    source = item.get("source", "Global Media")
    pub_raw = item.get("published", "")
    
    indonesian_title = synthesize_indonesian_headline(original_title)
    category = categorize_news(original_title)
    pub_time_wib = format_published_wib(pub_raw)
    is_important = is_important_news(original_title)
    
    # Generate 3 structured institutional paragraphs tailored to category
    p1 = f"Laporan pasar global terverifikasi dari {source} menyoroti dinamika: '{original_title}'. Pelaku pasar institusional saat ini mencermati pergeseran arus likuiditas dan sentimen risiko lintas aset."
    if category == "Kebijakan The Fed & Inflasi":
        p2 = "Dari perspektif transmisi moneter, proyeksi suku bunga acuan The Fed dan data inflasi acuan (CPI/PCE) menjadi jangkar utama penentuan valuasi aset berimbal hasil obligasi AS."
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

    paragraphs = [p1, p2, p3]
    
    # Pass clean text for targeted AI interpretation
    full_text_for_ai = f"{original_title}. Kategori: {category}. Sumber: {source}."
    interpretation = interpret_single_news_item(full_text_for_ai)
    
    # Generate stable deterministic ID
    title_hash = hashlib.md5(original_title.encode("utf-8")).hexdigest()[:8]
    bulletin_id = f"novaire-wire-{title_hash}"
    
    return {
        "id": bulletin_id,
        "title": indonesian_title,
        "original_title": original_title,
        "source": source,
        "link": item.get("link", ""),
        "channel": "Novaire Macro Wire",
        "channel_badge": "Novaire Desk",
        "category": category,
        "published_time": pub_time_wib,
        "is_important": is_important,
        "paragraphs": paragraphs,
        "interpretation": interpretation
    }

def get_daily_macro_bulletins(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns structured daily macro news bulletins formatted like channel briefs with rich interpretations.
    Automatically fetches live feeds, synthesizes new bulletins, merges, and persists to data/daily_bulletins.json.
    """
    BULLETINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Read existing cached bulletins if fresh
    cached_bulletins = []
    cache_time = 0
    if BULLETINS_FILE.exists():
        try:
            with open(BULLETINS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cache_time = data.get("cached_at", 0)
                    cached_bulletins = data.get("bulletins", [])
                elif isinstance(data, list):
                    cached_bulletins = data
        except Exception as e:
            print(f"[GeopoliticalService] Error reading daily bulletins cache: {e}")
            
    now_ts = datetime.now(timezone.utc).timestamp()
    # Cache is valid for 120 seconds (2 minutes) to ensure live news stays fresh
    if not force_refresh and cached_bulletins and (now_ts - cache_time < 120):
        return cached_bulletins

    # 2. Fetch fresh live news across macro queries
    raw_articles = []
    seen_titles = set()
    for q in MACRO_FEED_QUERIES:
        items = fetch_feed(q)
        for it in items:
            t_clean = it["title"].strip().lower()
            if t_clean not in seen_titles and len(t_clean) > 15:
                seen_titles.add(t_clean)
                raw_articles.append(it)
                
    # 3. Build new bulletins from fresh articles
    new_bulletins = []
    # Pick top fresh articles (up to 8 items)
    for art in raw_articles[:8]:
        try:
            b = generate_bulletin_from_feed_item(art)
            new_bulletins.append(b)
        except Exception as err:
            print(f"[GeopoliticalService] Error generating bulletin for article: {err}")

    # 4. Merge new bulletins with previous bulletins (deduplicating by title similarity)
    existing_pool = cached_bulletins if cached_bulletins else list(FALLBACK_BULLETINS)
    merged_bulletins = []
    seen_bulletin_titles = set()
    
    # Put new bulletins first
    for b in new_bulletins:
        t_key = b["title"].strip().lower()[:40]
        if t_key not in seen_bulletin_titles:
            seen_bulletin_titles.add(t_key)
            merged_bulletins.append(b)
            
    # Then append existing bulletins that haven't been seen
    for b in existing_pool:
        t_key = b["title"].strip().lower()[:40]
        if t_key not in seen_bulletin_titles:
            seen_bulletin_titles.add(t_key)
            merged_bulletins.append(b)
            
    # Sort with is_important first, while preserving recency
    merged_bulletins = sorted(merged_bulletins[:16], key=lambda x: (not x.get("is_important", False)))

    # If completely empty, fallback
    if not merged_bulletins:
        merged_bulletins = list(FALLBACK_BULLETINS)

    # 5. Save merged results to data/daily_bulletins.json
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
    if "impact_xau" in item and item.get("impact_note") and item.get("interpretation"):
        return item
    title_lower = item.get("title", "").lower()
    bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges"]
    bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise", "dollar strengthens"]
    
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
        impact_note = "Pengaruh terbatas, volatilitas pasar terkonsentrasi pada proyeksi FOMC."
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
                all_news.append(ensure_news_impact(item))
                
    if not all_news:
        all_news = [ensure_news_impact(dict(h)) for h in FALLBACK_HEADLINES]
        
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
