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
    datetime_wib = next_event.get("datetime_wib", "") if next_event else ""
    if not datetime_wib and next_event and "datetime" in next_event:
        from modules.calendar_service import format_wib_datetime
        datetime_wib = format_wib_datetime(next_event["datetime"])
    if not datetime_wib:
        datetime_wib = "Jadwal live ekonomi"
    
    # Header title depending on stage
    if stage == "pre_news":
        stage_title = f"📢 PRE-NEWS SIGNAL: {group_name}"
        stage_desc = f"**Peringatan rilis berita {group_name} dalam `{countdown_str}`.**\n📅 **Jadwal Rilis:** `{datetime_wib}`"
    elif stage == "imminent":
        stage_title = f"⚡ IMMINENT NEWS ALERT: {group_name}"
        stage_desc = f"**Rilis berita dalam hitungan menit ({countdown_str})! Siapkan manajemen risiko.**\n📅 **Jadwal Rilis:** `{datetime_wib}`"
    elif stage == "flash_release":
        stage_title = f"🔥 FLASH REACTION: {group_name} RELEASED"
        stage_desc = f"**Data resmi {group_name} telah dirilis. Analisis deviasi instan aktif.**\n📅 **Rilis:** `{datetime_wib}`"
    else:
        stage_title = f"📊 XAU/USD NEWS ANALYSIS: {group_name}"
        stage_desc = f"**Update terkini fundamental & geopolitik XAU/USD.**\n📅 **Jadwal Rilis:** `{datetime_wib}`"

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

    why_reason = signal.get("why_bias_reason", "")
    market_interp = signal.get("market_interpretation", "")

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
            "name": "⏱️ JADWAL & COUNTDOWN",
            "value": f"**{group_name}**\n⏳ `{countdown_str}`\n📅 `{datetime_wib}`",
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
        }
    ]

    if why_reason:
        fields.append({
            "name": f"💡 ALASAN BIAS FUNDAMENTAL ({group_name})",
            "value": why_reason[:1024],
            "inline": False
        })

    if market_interp:
        fields.append({
            "name": "🔍 TRANSMISI PASAR (DXY • YIELDS • XAU)",
            "value": market_interp[:1024],
            "inline": False
        })

    fields.append({
        "name": "🌍 INTELEJEN GEOPOLITIK & MAKRO",
        "value": f"> {reasoning}",
        "inline": False
    })

    embed = {
        "title": stage_title,
        "description": stage_desc,
        "color": color,
        "author": {
            "name": "EANews Novaire • Fundamental Signal Engine",
            "icon_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg"
        },
        "fields": fields,
        "footer": {
            "text": f"EANews Novaire Intelligence • Jadwal: {datetime_wib}",
            "icon_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg"
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
        "content": "@everyone 🚨 **HIGH IMPACT NEWS SIGNAL ALERT • EANEWS NOVAIRE**",
        "username": "EANews Novaire",
        "avatar_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg",
        "embeds": [embed],
        "allowed_mentions": {
            "parse": ["everyone"]
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EANewsNovaireBot/3.2"
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

def format_breaking_news_embed(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    interp = bulletin.get("interpretation", {})
    bias = interp.get("bias", "NEUTRAL")
    bias_badge = interp.get("bias_badge", "ANALISIS PASAR")
    
    if "SELL" in bias:
        color = COLOR_SELL
        bias_emoji = "🔻 🔴"
    elif "BUY" in bias:
        color = COLOR_BUY
        bias_emoji = "🔺 🟢"
    else:
        color = COLOR_NEUTRAL
        bias_emoji = "⚠️ 🟡"
        
    title = bulletin.get("title", "BERITA MAKRO TERBARU")
    channel = bulletin.get("channel", "Novaire Macro Wire")
    pub_time = bulletin.get("published_time", "Terbaru")
    category = bulletin.get("category", "Geopolitik & Makro")
    
    headline_analysis = interp.get("headline_analysis", "Analisis transmisi makro terhadap XAU/USD.")
    transmission = interp.get("transmission_mechanism", "Transmisi likuiditas dan sentimen safe-haven.")
    intermarket = interp.get("intermarket_matrix", {})
    tactical_action = interp.get("tactical_action", "Pantau level teknikal support/resisten utama.")
    
    paragraphs = bulletin.get("paragraphs", [])
    brief_text = paragraphs[0] if paragraphs else ""
    if len(brief_text) > 350:
        brief_text = brief_text[:350] + "..."

    matrix_lines = []
    if intermarket.get("oil"): matrix_lines.append(f"• **Minyak:** {intermarket['oil']}")
    if intermarket.get("yields"): matrix_lines.append(f"• **US 10Y Yield:** {intermarket['yields']}")
    if intermarket.get("dxy"): matrix_lines.append(f"• **Dolar (DXY):** {intermarket['dxy']}")
    if intermarket.get("xau"): matrix_lines.append(f"• **Emas (XAU/USD):** {intermarket['xau']}")
    matrix_str = "\n".join(matrix_lines) if matrix_lines else "• Reaksi pasar normal terukur."

    fields = [
        {
            "name": "🎯 EXPECTED XAU/USD BIAS",
            "value": f"### {bias_emoji} {bias} • {bias_badge}",
            "inline": False
        },
        {
            "name": "💡 ANALISIS KUNCI EKSEKUTIF",
            "value": headline_analysis[:1024],
            "inline": False
        },
        {
            "name": "🔄 MEKANISME TRANSMISI MAKRO (DXY • YIELD • XAU)",
            "value": transmission[:1024],
            "inline": False
        },
        {
            "name": "🌐 PROYEKSI PASAR GLOBAL (INTERMARKET)",
            "value": matrix_str[:1024],
            "inline": False
        },
        {
            "name": "🎯 PANDUAN TAKTIS TRADER",
            "value": tactical_action[:1024],
            "inline": False
        }
    ]

    if brief_text:
        fields.append({
            "name": "📰 RINGKASAN BERITA",
            "value": f"> {brief_text}",
            "inline": False
        })

    embed = {
        "title": f"🚨 [BREAKING WIRE & INTERPRETASI]: {title[:200]}",
        "description": f"**Kanal:** `{channel}` • ⏰ `{pub_time}`\n🏷️ **Kategori:** `{category}`",
        "color": color,
        "author": {
            "name": "EANews Novaire • Macro Wire Sentinel",
            "icon_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg"
        },
        "fields": fields,
        "footer": {
            "text": f"EANews Novaire Macro Sentinel • Waktu: {pub_time}",
            "icon_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return embed

def send_breaking_news_discord_webhook(webhook_url: str, bulletin: Dict[str, Any]) -> Dict[str, Any]:
    """Sends immediate Discord alert for high impact / breaking macro news and its AI interpretation."""
    if not webhook_url or not webhook_url.strip().startswith("http"):
        return {
            "success": False,
            "error": "URL Discord Webhook belum diisi atau tidak valid."
        }
        
    embed = format_breaking_news_embed(bulletin)
    payload = {
        "content": "@everyone 🚨 **BREAKING NEWS & INTERPRETASI PASAR XAU/USD • EANEWS NOVAIRE**",
        "username": "EANews Novaire Wire",
        "avatar_url": "https://raw.githubusercontent.com/TakatouValencia/ai-news-analisis/main/web/static/img/novaire_logo.jpg",
        "embeds": [embed],
        "allowed_mentions": {
            "parse": ["everyone"]
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EANewsNovaireBot/3.2"
    }
    
    req = urllib.request.Request(webhook_url.strip(), data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "success": resp.status in [200, 204],
                "status_code": resp.status,
                "message": "Alert Berita Penting berhasil dikirim ke Discord!"
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

