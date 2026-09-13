// EANews Analisis AI - Frontend Application Logic

let state = null;
let secondsRemaining = 0;

// Format seconds into "41m 57s" or "2h 15m 30s"
function formatCountdown(sec) {
  if (sec <= 0) return "Released / Imminent";
  const days = Math.floor(sec / 86400);
  const hours = Math.floor((sec % 86400) / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  
  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  } else if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  } else {
    return `${minutes}m ${seconds}s`;
  }
}

// Toast notification helper
function showToast(message, isError = false) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.style.borderColor = isError ? "#ef4444" : "#10b981";
  toast.innerHTML = `<span>${isError ? '⚠️' : '✅'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Update UI elements from state
function updateUI(data) {
  state = data;
  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  
  // 1. Bias Card
  const biasCard = document.getElementById("card-bias");
  const biasEl = document.getElementById("bias-value");
  const contextEl = document.getElementById("context-value");
  const scoreEl = document.getElementById("score-value");
  
  const bias = signal.expected_bias || "XAU NEUTRAL";
  biasEl.textContent = bias;
  
  biasCard.classList.remove("sell", "buy");
  if (bias.includes("SELL")) {
    biasCard.classList.add("sell");
  } else if (bias.includes("BUY")) {
    biasCard.classList.add("buy");
  }
  
  contextEl.textContent = `${signal.context_percent || 50}%`;
  const score = signal.xau_score || 0.0;
  scoreEl.textContent = score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  
  // 2. Next USD News Card
  const newsTitleEl = document.getElementById("next-news-title");
  const countdownEl = document.getElementById("countdown-value");
  const itemsContainer = document.getElementById("news-items-list");
  
  newsTitleEl.textContent = nextEvent.group_name || "USD High Impact";
  secondsRemaining = nextEvent.seconds_until || 0;
  countdownEl.textContent = formatCountdown(secondsRemaining);
  
  itemsContainer.innerHTML = "";
  if (nextEvent.items && nextEvent.items.length > 0) {
    nextEvent.items.forEach(it => {
      const row = document.createElement("div");
      row.className = "news-item-row";
      
      const figures = it.actual 
        ? `A: ${it.actual} · F: ${it.forecast} · P: ${it.previous}`
        : `F ${it.forecast} · P ${it.previous}`;
        
      row.innerHTML = `
        <span class="news-item-name">${it.title}</span>
        <span class="news-item-figures">${figures}</span>
      `;
      itemsContainer.appendChild(row);
    });
  } else {
    itemsContainer.innerHTML = `<div class="news-item-row"><span class="news-item-name">Menunggu rilis data...</span></div>`;
  }
  
  // 3. Spike Potential Card
  const spikeValEl = document.getElementById("spike-value");
  const spikeBar = document.getElementById("spike-bar");
  const spike = signal.spike_potential || 50;
  spikeValEl.textContent = `${spike}%`;
  spikeBar.style.width = `${spike}%`;
  
  // 4. One-Way Card
  const onewayValEl = document.getElementById("oneway-value");
  const onewayBar = document.getElementById("oneway-bar");
  const oneway = signal.one_way || 50;
  onewayValEl.textContent = `${oneway}%`;
  onewayBar.style.width = `${oneway}%`;
  
  // 5. Two-Way Card
  const twowayValEl = document.getElementById("twoway-value");
  const twowayBar = document.getElementById("twoway-bar");
  const twoway = signal.two_way || 50;
  twowayValEl.textContent = `${twoway}%`;
  twowayBar.style.width = `${twoway}%`;
  
  // 6. Geopolitical Sentiment & Reasoning
  const geoTagEl = document.getElementById("geo-sentiment-tag");
  const reasoningEl = document.getElementById("ai-reasoning");
  const geoSentiment = signal.geo_sentiment || "neutral";
  
  geoTagEl.className = `geo-tag tag-${geoSentiment}`;
  geoTagEl.textContent = `GEOPOLITIK: ${geoSentiment.toUpperCase()}`;
  reasoningEl.textContent = signal.ai_reasoning || "Analisis geopolitik dan deviasi fundamental sedang aktif.";

  // 7. Correlated Secondary News (Lead-in to Big News)
  const correlatedContainer = document.getElementById("correlated-news-container");
  if (correlatedContainer) {
    const correlatedList = data.correlated_news || [];
    if (correlatedList.length > 0) {
      correlatedContainer.innerHTML = "";
      correlatedList.forEach(item => {
        const itemEl = document.createElement("div");
        itemEl.className = "correlated-item";
        
        const impactClass = item.impact_type === "buy" ? "impact-buy" : (item.impact_type === "sell" ? "impact-sell" : "impact-neutral");
        const impactIcon = item.impact_type === "buy" ? "🟢" : (item.impact_type === "sell" ? "🔴" : "🟡");
        
        itemEl.innerHTML = `
          <div class="correlated-header">
            <span class="correlated-title">${item.title}</span>
            <span class="badge-tag">${item.category}</span>
          </div>
          ${item.latest_data ? `<div class="correlated-data-row">📊 ${item.latest_data} · ${item.status || ''}</div>` : ''}
          <div class="correlated-desc">${item.relation_note}</div>
          <div class="correlated-footer">
            <span class="impact-text ${impactClass}">${impactIcon} ${item.bias_impact}</span>
            <span class="importance-badge">${item.importance}</span>
          </div>
        `;
        correlatedContainer.appendChild(itemEl);
      });
    }
  }

  // 8. Breaking Geopolitical News Feed
  const geoContainer = document.getElementById("geopolitical-news-container");
  if (geoContainer) {
    const newsList = data.news || [];
    if (newsList.length > 0) {
      geoContainer.innerHTML = "";
      newsList.slice(0, 6).forEach(news => {
        const newsEl = document.createElement("div");
        newsEl.className = "news-feed-item";
        
        const impact = news.impact_xau || "NEUTRAL";
        const impactClass = impact.includes("BUY") ? "badge-impact-buy" : (impact.includes("SELL") ? "badge-impact-sell" : "badge-impact-neutral");
        
        newsEl.innerHTML = `
          <div class="news-feed-header">
            <div class="news-headline">${news.title}</div>
            <span class="badge-impact ${impactClass}">${impact}</span>
          </div>
          ${news.impact_note ? `<div class="news-ai-note">💡 <strong>Analisa XAU:</strong> ${news.impact_note}</div>` : ''}
          <div class="news-meta-row">
            <span class="news-source-tag">${news.source || 'Global Wire'}</span>
            <span class="news-time-tag">${news.published || 'Terbaru'}</span>
          </div>
        `;
        geoContainer.appendChild(newsEl);
      });
    }
  }

  // 9. Sync indicator pulse
  const syncBadge = document.getElementById("live-status-badge");
  if (syncBadge) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const syncText = document.getElementById("sync-status-text");
    if (syncText) syncText.textContent = `LIVE (${timeStr} WIB)`;
  }
}

// Fetch live state from API
async function fetchState(force = false) {
  try {
    const res = await fetch(`/api/state?force=${force}`);
    if (res.ok) {
      const data = await res.json();
      updateUI(data);
    }
  } catch (err) {
    console.error("Error fetching state:", err);
  }
}

// Manual force refresh
async function handleRefresh() {
  const btn = document.getElementById("btn-refresh");
  btn.style.transform = "rotate(180deg)";
  showToast("Memperbarui kalender ekonomi & berita...");
  
  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    if (res.ok) {
      const resp = await res.json();
      updateUI(resp.data);
      showToast("Data terbaru berhasil diperbarui!");
    }
  } catch (err) {
    showToast("Gagal memperbarui data: " + err, true);
  } finally {
    setTimeout(() => { btn.style.transform = "none"; }, 500);
  }
}

// Send test signal to Discord Webhook
async function handleSendDiscord() {
  const btn = document.getElementById("btn-send-discord");
  const originalText = btn.innerHTML;
  btn.innerHTML = `<span>⏳ Mengirim ke Discord (@everyone)...</span>`;
  btn.disabled = true;
  
  try {
    const res = await fetch("/api/trigger-discord", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: "pre_news" })
    });
    const result = await res.json();
    
    if (result.success) {
      showToast("Sinyal & ping @everyone berhasil dikirim ke Discord!");
    } else {
      showToast("Gagal kirim: " + (result.error || "Cek log server"), true);
    }
  } catch (err) {
    showToast("Kesalahan jaringan: " + err, true);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// Second-by-second local countdown ticker
setInterval(() => {
  if (secondsRemaining > 0) {
    secondsRemaining -= 1;
    const countdownEl = document.getElementById("countdown-value");
    if (countdownEl) {
      countdownEl.textContent = formatCountdown(secondsRemaining);
    }
  }
}, 1000);

// Auto-sync state every 15 seconds
setInterval(() => {
  fetchState(false);
}, 15000);

// Setup Event Listeners on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-refresh").addEventListener("click", handleRefresh);
  document.getElementById("btn-send-discord").addEventListener("click", handleSendDiscord);
  
  // Initial load
  fetchState(true);
});
