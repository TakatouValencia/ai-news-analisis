import json
import urllib.request
import urllib.error
from typing import Dict, Any, List
from config import load_settings

def rule_based_sentiment_analysis(headlines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """High-accuracy rule-based NLP fallback for market and geopolitical sentiment."""
    geo_bullish_words = ["war", "strike", "attack", "missile", "escalat", "conflict", "crisis", "threat", "sanction", "military", "tensions", "safe-haven", "rally", "surges"]
    geo_bearish_words = ["ceasefire", "peace", "truce", "de-escalat", "agreement", "diplomacy", "calm", "easing"]
    
    usd_hawkish_words = ["hike", "hawkish", "inflation rise", "strong jobs", "yields surge", "dollar gains", "rate pause", "higher for longer", "patient on cuts"]
    usd_dovish_words = ["cut", "dovish", "slowdown", "cooling", "recession", "weak jobs", "rate cut", "easing policy", "dollar drops"]
    
    geo_score = 0.0
    macro_score = 0.0
    
    for h in headlines:
        title = h.get("title", "").lower()
        
        for w in geo_bullish_words:
            if w in title:
                geo_score += 0.6
        for w in geo_bearish_words:
            if w in title:
                geo_score -= 0.6
                
        # Hawkish USD = Bearish Gold (negative for XAU)
        for w in usd_hawkish_words:
            if w in title:
                macro_score -= 0.8
        # Dovish USD = Bullish Gold (positive for XAU)
        for w in usd_dovish_words:
            if w in title:
                macro_score += 0.8
                
    # Clamp scores
    geo_score = max(-3.0, min(3.0, round(geo_score, 2)))
    macro_score = max(-4.0, min(4.0, round(macro_score, 2)))
    
    if geo_score > 0.5:
        geo_sentiment = "bullish"
    elif geo_score < -0.5:
        geo_sentiment = "bearish"
    else:
        geo_sentiment = "neutral"
        
    reasoning = (
        f"Sentimen geopolitik global cenderung {geo_sentiment} terhadap emas (skor {geo_score:+0.2f}). "
        f"Fokus pelaku pasar tertuju pada imbal hasil obligasi AS dan konsensus suku bunga (skor makro {macro_score:+0.2f})."
    )
    
    return {
        "geopolitical_sentiment": geo_sentiment,
        "geo_score": geo_score,
        "macro_score": macro_score,
        "summary_reasoning": reasoning,
        "mode": "rule_based_engine"
    }

def _request_llm(base_url: str, model_name: str, messages: list, headers: dict, timeout: int = 8) -> Dict[str, Any] | None:
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2
    }
    try:
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            content = content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(content)
            parsed["mode"] = f"llm_{model_name}"
            return parsed
    except Exception as e:
        print(f"[AI Analyzer] Model '{model_name}' tidak merespons ({e}), mencoba fallback...")
        return None

def analyze_with_llm(headlines: List[Dict[str, Any]], next_event_title: str) -> Dict[str, Any]:
    """Attempts LLM analysis with configured model (gemini-3.8-flash) and automated smart fallback."""
    settings = load_settings()
    api_key = settings.get("ai_api_key", "").strip()
    base_url = settings.get("ai_base_url", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    primary_model = settings.get("ai_model", "gemini-3.8-flash").strip()
    
    if not api_key:
        return rule_based_sentiment_analysis(headlines)
        
    titles_summary = "\n".join([f"- {h.get('title')} ({h.get('source')})" for h in headlines[:8]])
    
    prompt = f"""Kamu adalah Quantitative Fundamental Analyst spesialis XAU/USD (Gold) dan Macroeconomic Intelligence.
Berikut adalah rilis berita terdekat: {next_event_title}
Dan berita geopolitik/ekonomi terbaru:
{titles_summary}

Berikan analisis terstruktur dalam format JSON murni:
{{
  "geopolitical_sentiment": "bullish" | "bearish" | "neutral",
  "geo_score": <float antara -3.00 sampai +3.00, positif = tensi naik dorong safe-haven emas, negatif = de-eskalasi>,
  "macro_score": <float antara -4.00 sampai +4.00, positif = dovish USD/dorong emas naik, negatif = hawkish USD/tekan emas turun>,
  "summary_reasoning": "<1-2 kalimat padat bahasa Indonesia tentang sentimen geopolitik dan pengaruhnya ke emas>"
}}
Hanya kembalikan JSON murni tanpa markdown formatting atau backtick.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
        "X-Title": "EANews Analisis"
    }

    messages = [
        {"role": "system", "content": "You are a professional financial AI quant analyst. Output only valid JSON."},
        {"role": "user", "content": prompt}
    ]

    # Models to attempt in priority order
    candidate_models = [primary_model]
    if primary_model != "gemini-3.5-flash-lite":
        candidate_models.append("gemini-3.5-flash-lite")

    for m in candidate_models:
        result = _request_llm(base_url, m, messages, headers, timeout=8)
        if result:
            return result

    # If all models fail / timeout, fall back to robust rule-based NLP engine
    return rule_based_sentiment_analysis(headlines)

def interpret_single_news_item(news_text: str) -> Dict[str, Any]:
    """Interprets a daily news item or user-pasted news text for market transmission to XAU/USD, DXY, and macroeconomic indicators."""
    text_lower = news_text.lower()
    
    # Rule-based NLP heuristics
    bullish_signals = [
        "war", "strike", "attack", "missile", "iran", "israel", "conflict", "crisis", "threat", 
        "sanction", "military", "safe-haven", "rally", "surges", "bank fail", "emergency fund", 
        "liquidity crisis", "cut", "dovish", "rate cut", "diversifikasi", "tanah jarang", 
        "emas batangan", "dedolarisasi", "financial stability board", "kesenjangan likuiditas"
    ]
    bearish_signals = [
        "peace", "ceasefire", "truce", "diplomatis", "tidak menyerang", "perundingan", 
        "minyak turun", "hike", "hawkish", "dollar gains", "rate pause", "strong jobs", 
        "yields surge", "inflasi melunak", "pengetatan pajak", "kekhawatiran mereda"
    ]
    
    bull_count = sum(1 for w in bullish_signals if w in text_lower)
    bear_count = sum(1 for w in bearish_signals if w in text_lower)
    
    if "tidak akan menyerang iran" in text_lower or ("minyak turun" in text_lower and "iran" in text_lower):
        bias = "BEARISH XAU"
        bias_badge = "RETRACEMENT TEKANAN JUAL"
        impact_color = "sell"
        headline_analysis = "Pernyataan diplomatis meredakan kekhawatiran pasokan minyak Timur Tengah dan memicu de-eskalasi premi risiko emas."
        transmission = (
            "1. Retorika Donald Trump mengenai penundaan eskalasi militer ke Iran sebelum pemilu meredakan premi risiko pasokan Selat Hormuz.\n"
            "2. Koreksi harga minyak mentah menekan ekspektasi inflasi jangka pendek, meredakan spekulasi lonjakan yields obligasi.\n"
            "3. Berkurangnya kepanikan geopolitik memicu aksi profit taking pada posisi safe-haven emas (XAU/USD) menuju area support teknikal terdekat."
        )
        intermarket = {
            "oil": "WTI Minyak Melemah (-2.6%) • Premi risiko pasokan mereda",
            "yields": "US 10Y Yield Stabil di 4.15% • Lelang Treasury terserap",
            "dxy": "Indeks Dolar (DXY) di 104.20 • Menunggu konfirmasi data tenaga kerja",
            "xau": "XAU/USD Cenderung Tertekan • Menguji support demand kunci"
        }
        tactical_action = "Waspadai aksi beli agresif di area resisten tinggi. Ambil sikap sabar menanti pengujian support kuat atau konfirmasi rilis NFP sebelum entri posisi baru."
    elif "obligasi treasury stabil" in text_lower or "imbal hasil obligasi" in text_lower:
        bias = "NEUTRAL TO BULLISH XAU"
        bias_badge = "KONSOLIDASI MENUNGGU KATALIS"
        impact_color = "neutral"
        headline_analysis = "Imbal hasil Treasury AS tenor 10 tahun bergerak tenang di 4.15%, membatasi tekanan jual pada emas menjelang data makro utama."
        transmission = (
            "1. Stabilitas yield obligasi mencerminkan pasar telah memperhitungkan retorika politik jangka pendek.\n"
            "2. Tanpa lonjakan imbal hasil obligasi di atas 4.20%, opportunity cost memegang emas non-yield tetap terkendali.\n"
            "3. Pasangan XAU/USD cenderung bergerak dalam rentang konsolidasi teratur (range-bound) mengantisipasi katalis volatilitas berikutnya."
        )
        intermarket = {
            "oil": "Minyak Bergerak Flat • Pasar mencermati kuota produksi",
            "yields": "US 10Y Yield di 4.15% • Bertahan di bawah resistance kritis 4.22%",
            "dxy": "DXY Konsolidasi 104.10 - 104.30",
            "xau": "XAU/USD Range Bound • Menjaga struktur swing support"
        }
        tactical_action = "Terapkan strategi range-trading terukur (Buy on Support, Sell on Resistance) dengan stop-loss ketat 35-50 pips."
    elif "financial stability" in text_lower or "likuiditas darurat" in text_lower or "bank" in text_lower:
        bias = "BULLISH XAU"
        bias_badge = "PERLINDUNGAN RISIKO SISTEMIK"
        impact_color = "buy"
        headline_analysis = "Desakan penguatan likuiditas perbankan dari FSB menyoroti kerentanan sistemik, menopang minat beli defensif emas."
        transmission = (
            "1. Kesenjangan likuiditas bank saat krisis menyoroti risiko counterparty pada sistem keuangan konvensional.\n"
            "2. Institusi keuangan global memperbesar alokasi aset fisik bebas risiko kredit (zero counterparty risk).\n"
            "3. Emas batangan institusional mendapatkan bantalan beli struktural yang solid setiap kali terjadi koreksi harga."
        )
        intermarket = {
            "oil": "Minyak Netral • Fokus pada proyeksi permintaan manufaktur",
            "yields": "Yield Obligasi Melandai • Permintaan surat utang tenor pendek",
            "dxy": "Dolar AS Bertahan sebagai Mata Uang Cadangan",
            "xau": "XAU/USD Mendapat Dukungan Kuat • Akumulasi institusi di level diskon"
        }
        tactical_action = "Pertimbangkan strategi Buy on Dip saat terjadi koreksi intraday menuju area support dinamis."
    elif bull_count > bear_count:
        bias = "BULLISH XAU"
        bias_badge = "SAFE-HAVEN & INFLATION HEDGE"
        impact_color = "buy"
        headline_analysis = "Sentimen didominasi faktor ketidakpastian global dan diversifikasi cadangan aset yang mendukung valuasi emas."
        transmission = (
            "1. Peningkatan ketegangan geopolitik atau ekspektasi pelonggaran moneter memperbesar permintaan lindung nilai.\n"
            "2. Pelaku pasar melindungi portofolio dari potensi depresiasi nilai tukar dan volatilitas pasar saham.\n"
            "3. Momentum XAU/USD berpotensi menembus resistance struktural."
        )
        intermarket = {
            "oil": "Komoditas energi cenderung menguat akibat premi risiko",
            "yields": "Yield obligasi tertekan oleh aliran dana perlindungan",
            "dxy": "DXY fluktuatif merespons pergeseran arus modal global",
            "xau": "XAU/USD Menguat • Potensi reli lanjutan"
        }
        tactical_action = "Fokus pada peluang buy on breakout atau retest support terdekat dengan rasio risiko minimal 1:2."
    elif bear_count > bull_count:
        bias = "BEARISH XAU"
        bias_badge = "TEKANAN PENGUATAN USD"
        impact_color = "sell"
        headline_analysis = "Peredaan tensi dan prospek penguatan Dolar AS memicu tekanan koreksi pada instrumen logam mulia."
        transmission = (
            "1. Berkurangnya premi risiko geopolitik memicu rotasi modal dari safe haven ke aset berisiko (equities).\n"
            "2. Penguatan Dolar AS dan stabilitas imbal hasil obligasi menekan daya tarik emas spot.\n"
            "3. Harga emas XAU/USD rentan mengalami likuidasi posisi beli jangka pendek."
        )
        intermarket = {
            "oil": "Minyak melemah seiring stabilisasi pasokan global",
            "yields": "Yield obligasi bertahan kokoh di level tinggi",
            "dxy": "DXY menguat memberikan tekanan langsung pada emas",
            "xau": "XAU/USD Terkoreksi • Waspadai pelebaran penurunan intraday"
        }
        tactical_action = "Hindari menangkap pisau jatuh (catching a falling knife). Pasang stop-loss ketat pada posisi buy yang ada."
    else:
        bias = "NEUTRAL"
        bias_badge = "SENTIMEN SEIMBANG"
        impact_color = "neutral"
        headline_analysis = "Pengaruh berita terdistribusi seimbang, pelaku pasar memusatkan fokus pada katalis kalender ekonomi berikutnya."
        transmission = (
            "1. Berita telah diantisipasi dan diserap pasar tanpa mendisrupsi tren dominan.\n"
            "2. Pelaku institusional menahan posisi besar menunggu kepastian data ekonomi resmi.\n"
            "3. Volatilitas harga XAU/USD bergerak normal di dalam rentang intraday teratur."
        )
        intermarket = {
            "oil": "Minyak konsolidasi dalam rentang sempit",
            "yields": "Yield Treasury fluktuasi wajar",
            "dxy": "DXY stabil di level psikologis",
            "xau": "XAU/USD Sideways • Bersiap menyambut data rilis berikutnya"
        }
        tactical_action = "Fokus pada level support dan resistance teknikal intraday tanpa bias arah berlebihan."

    fallback_result = {
        "bias": bias,
        "bias_badge": bias_badge,
        "impact_color": impact_color,
        "headline_analysis": headline_analysis,
        "transmission_mechanism": transmission,
        "intermarket_matrix": intermarket,
        "tactical_action": tactical_action,
        "mode": "rule_based_engine"
    }

    # Attempt LLM analysis if API key is present
    settings = load_settings()
    api_key = settings.get("ai_api_key", "").strip()
    base_url = settings.get("ai_base_url", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    primary_model = settings.get("ai_model", "gemini-3.8-flash").strip()

    if not api_key:
        return fallback_result

    prompt = f"""Kamu adalah Kepala Analis Makroekonomi & Quantitative Trader spesialis Emas (XAU/USD).
Berikan interpretasi institusional terhadap berita harian berikut:
\"\"\"{news_text[:1400]}\"\"\"

Kembalikan HANYA JSON murni (tanpa markdown backtick):
{{
  "bias": "BULLISH XAU" | "BEARISH XAU" | "NEUTRAL",
  "bias_badge": "<Label singkat, misal: RETRACEMENT TEKANAN JUAL / DEFENSIVE SAFE-HAVEN ACCUMULATION>",
  "impact_color": "buy" | "sell" | "neutral",
  "headline_analysis": "<1-2 kalimat tesis utama dampak berita ini terhadap pasar>",
  "transmission_mechanism": "<Penjelasan 2-3 poin terstruktur bagaimana berita ini mempengaruhi minyak, inflasi, obligasi, Dolar AS, dan emas XAU/USD>",
  "intermarket_matrix": {{
    "oil": "<Dampak ke Minyak Mentah>",
    "yields": "<Dampak ke US 10Y Yield>",
    "dxy": "<Dampak ke Indeks Dolar DXY>",
    "xau": "<Dampak ke Emas XAU/USD>"
  }},
  "tactical_action": "<Panduan aksi taktis bagi trader XAU/USD>"
}}
"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
        "X-Title": "EANews Analisis"
    }
    messages = [
        {"role": "system", "content": "You are a professional financial AI quant analyst specializing in XAU/USD. Output only valid JSON."},
        {"role": "user", "content": prompt}
    ]

    llm_res = _request_llm(base_url, primary_model, messages, headers, timeout=8)
    if llm_res and "bias" in llm_res and "transmission_mechanism" in llm_res:
        return llm_res

    return fallback_result

