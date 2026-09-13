import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional

COLOR_SELL = 0xEF4444  # Vivid Red
COLOR_BUY = 0x10B981   # Vivid Green
COLOR_NEUTRAL = 0xF59E0B # Vivid Amber

def format_embed(signal: Dict[str, Any], next_event: Optional[Dict[str, Any]], stage: str = "pre_news") -> Dict[str, Any]:
    bias = signal.get("expected_bias", "XAU NEUTRAL")
    context_pct = signal.get("context_percent", 50)
    xau_score = signal.get("xau_score", 0.0)
    spike = signal.get("spike_potential", 50)
    one_way = signal.get("one_way", 50)
    two_way = signal.get("two_way", 50)
    reasoning = signal.get("ai_reasoning", "Analisis konsensus fundamental dan geopolitik.")
    
    if "SELL" in bias:
        color = COLOR_SELL
        bias_emoji = "🔻 🔴"
    elif "BUY" in bias:
        color = COLOR_BUY
        bias_emoji = "🔺 🟢"
    else:
        color = COLOR_NEUTRAL
        bias_emoji = "⚠️ 🟡"
        
    group_name = next_event.get("group_name", "USD News") if next_event else "USD News"
    countdown_str = next_event.get("countdown_str", "Imminent") if next_event else "Imminent"
    
    # Header title depending on stage
    if stage == "pre_news":
        stage_title = f"📢 PRE-NEWS SIGNAL: {group_name}"
        stage_desc = f"**Peringatan rilis berita ekonomi High Impact USD dalam {countdown_str}.**"
    elif stage == "imminent":
        stage_title = f"⚡ IMMINENT NEWS ALERT: {group_name}"
        stage_desc = f"**Rilis berita dalam hitungan menit ({countdown_str})! Siapkan manajemen risiko.**"
    elif stage == "flash_release":
        stage_title = f"🔥 FLASH REACTION: {group_name} RELEASED"
        stage_desc = "**Data resmi telah dirilis. Analisis deviasi instan aktif.**"
    else:
        stage_title = f"📊 XAU/USD NEWS ANALYSIS: {group_name}"
        stage_desc = "**Update terkini fundamental & geopolitik XAU/USD.**"

    # Format event items
    items_text = []
    if next_event and "items" in next_event:
        for it in next_event["items"]:
            f = it.get("forecast", "-")
            p = it.get("previous", "-")
            a = it.get("actual", "")
            if a:
                items_text.append(f"• **{it.get('title')}**: `Actual: {a}` (F: {f} | P: {p})")
            else:
                items_text.append(f"• **{it.get('title')}**: Forecast `{f}` | Previous `{p}`")
    consensus_val = "\n".join(items_text) if items_text else "Data konsensus belum tersedia."

    fields = [
        {
            "name": "🎯 EXPECTED XAUUSD BIAS",
            "value": f"### {bias_emoji} {bias}",
            "inline": True
        },
        {
            "name": "📈 CONTEXT & SCORE",
            "value": f"**Context:** `{context_pct}%`\n**XAU Score:** `{xau_score:+0.2f}`",
            "inline": True
        },
        {
            "name": "⏱️ COUNTDOWN & EVENT",
            "value": f"**{group_name}** (`{countdown_str}`)",
            "inline": True
        },
        {
            "name": "📋 DATA KONSENSUS (F vs P)",
            "value": consensus_val,
            "inline": False
        },
        {
            "name": "⚡ POTENSI SPIKE (VOLATILITAS)",
            "value": f"**{spike}%**" + (" 🚨 [EXTREME VOLATILITY]" if spike >= 90 else " ⚠️ [HIGH VOLATILITY]"),
            "inline": True
        },
        {
            "name": "🔄 PROBABILITAS TRAJEKTORI",
            "value": f"**One-Way:** `{one_way}%`\n**Two-Way:** `{two_way}%`",
            "inline": True
        },
        {
            "name": "🌍 INTELEJEN GEOPOLITIK & MAKRO",
            "value": f"> {reasoning}",
            "inline": False
        }
    ]

    embed = {
        "title": stage_title,
        "description": stage_desc,
        "color": color,
        "fields": fields,
        "footer": {
            "text": "EANews Intelligence • XAU/USD Fundamental Specialist"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return embed

def send_discord_webhook(webhook_url: str, signal: Dict[str, Any], next_event: Optional[Dict[str, Any]], stage: str = "pre_news") -> Dict[str, Any]:
    if not webhook_url or not webhook_url.strip().startswith("http"):
        return {
            "success": False,
            "error": "URL Discord Webhook belum diisi atau tidak valid. Silakan atur di Pengaturan."
        }
        
    embed = format_embed(signal, next_event, stage)
    payload = {
        "content": "@everyone 🚨 **HIGH IMPACT NEWS SIGNAL ALERT**",
        "username": "EANews AI Analisis",
        "avatar_url": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=128&auto=format&fit=crop&q=80",
        "embeds": [embed],
        "allowed_mentions": {
            "parse": ["everyone"]
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EANewsBot/2.0"
    }
    
    req = urllib.request.Request(webhook_url.strip(), data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "success": resp.status in [200, 204],
                "status_code": resp.status,
                "message": "Sinyal berhasil dikirim ke Discord!"
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return {
            "success": False,
            "status_code": e.code,
            "error": f"HTTP {e.code}: {body}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
