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

def analyze_with_llm(headlines: List[Dict[str, Any]], next_event_title: str) -> Dict[str, Any]:
    """Attempts LLM analysis via configured API (OpenRouter/OpenAI), with automated fallback."""
    settings = load_settings()
    api_key = settings.get("ai_api_key", "").strip()
    base_url = settings.get("ai_base_url", "https://openrouter.ai/api/v1").rstrip("/")
    model = settings.get("ai_model", "google/gemini-2.5-flash")
    
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
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional financial AI quant analyst. Output only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"} if "gemini" not in model else None
    }
    
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}
    
    try:
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            # Clean possible markdown wrapping
            content = content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(content)
            parsed["mode"] = f"llm_{model}"
            return parsed
    except Exception as e:
        # Graceful fallback
        return rule_based_sentiment_analysis(headlines)
