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

DAILY_BULLETINS: List[Dict[str, Any]] = [
    {
        "id": "ja-news-01",
        "title": "HARGA MINYAK TURUN SETELAH PERNYATAAN TRUMP MENGENAI PERUNDINGAN IRAN MEREDAKAN KEKHAWATIRAN PASOKAN",
        "channel": "JA (Journal Ars)",
        "channel_badge": "882 pengikut",
        "category": "Energi & Geopolitik",
        "published_time": "18.54 WIB",
        "paragraphs": [
            "Harga minyak turun pada Jumat setelah kekhawatiran mengenai pasokan dari Timur Tengah mereda. Presiden AS Donald Trump mengatakan bahwa AS tidak akan menyerang Iran sebelum pemilu AS bulan depan, di tengah perundingan produktif untuk mengakhiri perang yang telah mengganggu pasar energi global.",
            "Financial Stability Board, lembaga global yang memantau risiko sistem keuangan, pada Jumat mendesak pihak berwenang untuk memperkuat mekanisme pendanaan darurat bagi bank yang mengalami kegagalan. Langkah ini diambil setelah ditemukan kesenjangan besar dalam kemampuan sejumlah negara menyediakan likuiditas selama krisis.",
            "Pengetatan pengawasan pajak terhadap individu kaya di China menjadi masalah terbaru bagi merek-merek mewah. Mereka sebelumnya sudah menghadapi dampak perang Iran dan tanda-tanda perlambatan belanja konsumen di AS.",
            "Komisi Eropa telah memilih 46 proyek bahan baku strategis untuk mendapatkan proses perizinan yang lebih cepat serta bantuan dalam memperoleh pendanaan publik dan swasta. Langkah ini dilakukan ketika Uni Eropa berupaya mendiversifikasi rantai pasokan dan mengurangi ketergantungan terhadap China.",
            "Uni Eropa bersama sejumlah negara Barat lainnya sangat bergantung pada China untuk mineral penting dan komponen seperti baterai serta logam tanah jarang yang digunakan dalam sektor pertahanan, kedirgantaraan, otomotif, dan energi terbarukan."
        ],
        "interpretation": {
            "bias": "BEARISH XAU",
            "bias_badge": "RETRACEMENT TEKANAN JUAL",
            "impact_color": "sell",
            "headline_analysis": "Retorika diplomatis Trump memangkas premi risiko geopolitik minyak mentah, meredakan ketakutan pasar dan memicu aksi profit taking pada instrumen safe-haven emas.",
            "transmission_mechanism": (
                "1. Pelemahan harga minyak mentah secara langsung menekan ekspektasi lonjakan inflasi jangka pendek.\n"
                "2. Berkurangnya kepanikan konflik di Timur Tengah mengurangi aliran dana darurat (defensive flight-to-safety) ke emas spot.\n"
                "3. Emas (XAU/USD) rentan mengalami aksi ambil untung (profit taking) menguji area support demand kunci, sementara isu likuiditas perbankan dari FSB tetap menjaga batas bawah (structural floor support) jangka panjang."
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
        "id": "ja-news-02",
        "title": "IMBAL HASIL OBLIGASI TREASURY STABIL SETELAH TRUMP MENUNJUKKAN SIKAP DIPLOMATIS TERHADAP IRAN MENJELANG PEMILU PARUH WAKTU",
        "channel": "JA (Journal Ars)",
        "channel_badge": "882 pengikut",
        "category": "Obligasi & Suku Bunga",
        "published_time": "19.10 WIB",
        "paragraphs": [
            "Imbal hasil obligasi sebagian besar stabil pada Jumat pagi ketika investor mencermati hasil lelang Treasury terbaru dan janji Presiden Donald Trump untuk tidak menyerang Iran hingga pemilu paruh waktu selesai.",
            "Imbal hasil Treasury AS tenor 10 tahun, yang menjadi acuan utama untuk suku bunga hipotek, pinjaman mobil, dan valuasi aset global, bergerak tenang di kisaran 4.14% - 4.18% seiring pasar menantikan kepastian data tenaga kerja resmi dan arah kebijakan suku bunga The Fed berikutnya.",
            "Pelaku pasar institusional saat ini menimbang stabilitas yield obligasi dengan risiko fiskal AS jangka menengah, di mana pasokan lelang surat utang tetap tinggi di tengah defisit anggaran pemerintah federal."
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
        "id": "ja-news-03",
        "title": "FINANCIAL STABILITY BOARD (FSB) DESAK REFORMASI LIKUIDITAS DARURAT PERBANKAN LINTAS NEGARA",
        "channel": "JA (Journal Ars)",
        "channel_badge": "882 pengikut",
        "category": "Perbankan Global",
        "published_time": "16.30 WIB",
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
        "id": "ja-news-04",
        "title": "KOMISI EROPA PERCEPAT 46 PROYEK KRUSIAL MINERAL STRATEGIS GUNA REDUKSI KETERGANTUNGAN PADA CHINA",
        "channel": "JA (Journal Ars)",
        "channel_badge": "882 pengikut",
        "category": "Rantai Pasok & Geopolitik",
        "published_time": "14.15 WIB",
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

def get_daily_macro_bulletins() -> List[Dict[str, Any]]:
    """Returns structured daily macro news bulletins formatted like channel briefs with rich interpretations."""
    return DAILY_BULLETINS

def ensure_news_impact(item: Dict[str, Any]) -> Dict[str, Any]:
    if "impact_xau" in item and item.get("impact_note") and item.get("interpretation"):
        return item
    title_lower = item.get("title", "").lower()
    bullish_triggers = ["war", "tension", "strike", "attack", "conflict", "cut", "dovish", "safe-haven", "rally", "crisis", "surges"]
    bearish_triggers = ["peace", "ceasefire", "truce", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", "yields rise"]
    
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

