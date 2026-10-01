// ==========================================================================
// EANews AI Analisis - Executive Frontend Engine Logic
// ==========================================================================

let state = null;
let secondsRemaining = 0;

// Format seconds into breakdown { days, hours, minutes, seconds }
function getCountdownParts(sec) {
  if (sec <= 0) return { days: 0, hours: 0, minutes: 0, seconds: 0 };
  const days = Math.floor(sec / 86400);
  const hours = Math.floor((sec % 86400) / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  return { days, hours, minutes, seconds };
}

function padZero(num) {
  return String(num).padStart(2, '0');
}

// Toast notification helper
function showToast(message, isError = false) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.style.borderColor = isError ? "rgba(244, 63, 94, 0.5)" : "rgba(16, 185, 129, 0.5)";
  toast.innerHTML = `<span>${isError ? '⚠️' : '✅'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// Update Real-Time Digital Clocks in Header
function updateClocks() {
  const now = new Date();
  
  // WIB (UTC+7)
  const wibStr = now.toLocaleTimeString("id-ID", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
  const clockWibEl = document.getElementById("clock-wib");
  if (clockWibEl) clockWibEl.textContent = `${wibStr} WIB`;

  // UTC
  const utcHours = String(now.getUTCHours()).padStart(2, '0');
  const utcMinutes = String(now.getUTCMinutes()).padStart(2, '0');
  const utcSeconds = String(now.getUTCSeconds()).padStart(2, '0');
  const clockUtcEl = document.getElementById("clock-utc");
  if (clockUtcEl) clockUtcEl.textContent = `${utcHours}:${utcMinutes}:${utcSeconds} UTC`;
}

// Update UI elements from live state data
function updateUI(data) {
  state = data;
  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  
  // 1. Expected Bias Card
  const biasCard = document.getElementById("card-bias");
  const biasEl = document.getElementById("bias-value");
  const symbolEl = document.getElementById("bias-symbol");
  const contextEl = document.getElementById("context-value");
  const contextBar = document.getElementById("context-bar");
  const scoreEl = document.getElementById("score-value");
  const scoreBar = document.getElementById("score-bar");
  const engineModeTag = document.getElementById("engine-mode-tag");
  
  const bias = signal.expected_bias || "XAU NEUTRAL";
  biasEl.textContent = bias;
  
  biasCard.classList.remove("sell", "buy");
  if (bias.includes("SELL")) {
    biasCard.classList.add("sell");
    symbolEl.textContent = "🔻";
  } else if (bias.includes("BUY")) {
    biasCard.classList.add("buy");
    symbolEl.textContent = "🔺";
  } else {
    symbolEl.textContent = "⚠️";
  }
  
  const contextPct = signal.context_percent || 75;
  contextEl.textContent = `${contextPct}%`;
  contextBar.style.width = `${contextPct}%`;
  
  const score = signal.xau_score || 0.0;
  scoreEl.textContent = score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  
  // Center-split score bar (-10.0 to +10.0 mapped to 0% - 100%)
  const scorePct = Math.max(5, Math.min(95, ((score + 10.0) / 20.0) * 100));
  scoreBar.style.width = `${scorePct}%`;
  
  if (engineModeTag && signal.analysis_mode) {
    engineModeTag.textContent = signal.analysis_mode.toUpperCase().replace("LLM_", "AI ");
  }

  // 2. Next USD News Primary Focus Card
  const newsTitleEl = document.getElementById("next-news-title");
  const scheduleEl = document.getElementById("next-news-schedule");
  const itemsContainer = document.getElementById("news-items-list");
  
  newsTitleEl.textContent = nextEvent.group_name || "USD High Impact News";
  if (scheduleEl) {
    scheduleEl.textContent = nextEvent.datetime_wib ? `Jadwal: ${nextEvent.datetime_wib}` : "Jadwal Resmi Sedang Dikonfirmasi";
  }
  
  secondsRemaining = nextEvent.seconds_until || 0;
  updateCountdownBoxes(secondsRemaining);
  
  itemsContainer.innerHTML = "";
  if (nextEvent.items && nextEvent.items.length > 0) {
    nextEvent.items.forEach(it => {
      const row = document.createElement("div");
      row.className = "news-item-row";
      
      const figures = it.actual 
        ? `A: ${it.actual} · F: ${it.forecast} · P: ${it.previous}`
        : `F: ${it.forecast} · P: ${it.previous}`;
        
      row.innerHTML = `
        <span class="news-item-name">${it.title}</span>
        <span class="news-item-figures">${figures}</span>
      `;
      itemsContainer.appendChild(row);
    });
  } else {
    itemsContainer.innerHTML = `<div class="news-item-row"><span class="news-item-name">Menunggu rilis data konsensus...</span></div>`;
  }
  
  // 3. Spike Potential Card
  const spikeValEl = document.getElementById("spike-value");
  const spikeBar = document.getElementById("spike-bar");
  const spikeTierBadge = document.getElementById("spike-tier-badge");
  const spike = signal.spike_potential || 50;
  
  spikeValEl.textContent = `${spike}%`;
  spikeBar.style.width = `${spike}%`;
  if (spikeTierBadge) {
    if (spike >= 90) {
      spikeTierBadge.textContent = "EXTREME";
      spikeTierBadge.className = "status-indicator-badge";
    } else if (spike >= 80) {
      spikeTierBadge.textContent = "VERY HIGH";
      spikeTierBadge.className = "status-indicator-badge badge-cyan";
    } else {
      spikeTierBadge.textContent = "HIGH";
      spikeTierBadge.className = "status-indicator-badge badge-purple";
    }
  }
  
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

  // 6. Upcoming Calendar List
  const upcomingListContainer = document.getElementById("upcoming-calendar-list");
  if (upcomingListContainer && data.calendar && data.calendar.upcoming_events) {
    const upcomingEvents = data.calendar.upcoming_events;
    if (upcomingEvents.length > 0) {
      upcomingListContainer.innerHTML = "";
      upcomingEvents.slice(0, 5).forEach((ev, idx) => {
        const itemEl = document.createElement("div");
        itemEl.className = "calendar-event-item" + (idx === 0 ? " event-active" : "");
        const figures = ev.items && ev.items.length > 0 && ev.items[0].forecast !== "-" 
          ? `F: ${ev.items[0].forecast} | P: ${ev.items[0].previous}` 
          : "";
        itemEl.innerHTML = `
          <div class="cal-event-top">
            <span class="cal-event-title">${ev.group_name}</span>
            <span class="pill-tag tag-high-impact">HIGH IMPACT</span>
          </div>
          <div class="cal-event-meta">
            <span class="cal-event-time">📅 ${ev.datetime_wib || ev.datetime}</span>
            <span class="cal-event-countdown">⏳ ${ev.countdown_str || ''}</span>
          </div>
          ${figures ? `<div class="cal-event-figures">📊 ${figures}</div>` : ''}
        `;
        upcomingListContainer.appendChild(itemEl);
      });
    } else {
      upcomingListContainer.innerHTML = `<div class="news-item-row"><span class="news-item-name">Tidak ada rilis berita High Impact mendatang minggu ini.</span></div>`;
    }
  }

  // 7. Correlated Secondary News (Lead-in to Big News)
  const correlatedLabel = document.getElementById("correlated-card-label");
  if (correlatedLabel) {
    correlatedLabel.textContent = `BERITA PENDUKUNG & INDIKATOR TERKAIT (LEAD-IN TO ${nextEvent.group_name || 'NEWS'})`;
  }
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
            <span class="pill-tag tag-engine">${item.category}</span>
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
  
  // 8. Geopolitical Sentiment & Synthesis
  const geoTagEl = document.getElementById("geo-sentiment-tag");
  const reasoningEl = document.getElementById("ai-reasoning");
  const geoSentiment = signal.geo_sentiment || "neutral";
  
  geoTagEl.className = `geo-tag tag-${geoSentiment}`;
  geoTagEl.textContent = `GEOPOLITIK: ${geoSentiment.toUpperCase()}`;
  reasoningEl.textContent = signal.ai_reasoning || "Analisis geopolitik dan deviasi fundamental sedang aktif.";

  // 9. Breaking Geopolitical Headlines
  const geoContainer = document.getElementById("geopolitical-news-container");
  if (geoContainer) {
    const newsList = data.news || [];
    if (newsList.length > 0) {
      geoContainer.innerHTML = "";
      newsList.slice(0, 5).forEach(news => {
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

  // 10. Sync indicator status
  const syncText = document.getElementById("sync-status-text");
  if (syncText) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    syncText.textContent = `LIVE (${timeStr} WIB)`;
  }
}

// Update the 4 digital blocks: DAYS : HOURS : MIN : SEC
function updateCountdownBoxes(sec) {
  const parts = getCountdownParts(sec);
  const daysEl = document.getElementById("cd-days");
  const hoursEl = document.getElementById("cd-hours");
  const minEl = document.getElementById("cd-minutes");
  const secEl = document.getElementById("cd-seconds");
  
  if (daysEl) daysEl.textContent = padZero(parts.days);
  if (hoursEl) hoursEl.textContent = padZero(parts.hours);
  if (minEl) minEl.textContent = padZero(parts.minutes);
  if (secEl) secEl.textContent = padZero(parts.seconds);
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

// Manual force refresh button
async function handleRefresh() {
  const btn = document.getElementById("btn-refresh");
  btn.style.transform = "rotate(180deg)";
  showToast("Menghubungkan & menyinkronkan data...");
  
  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    if (res.ok) {
      const resp = await res.json();
      updateUI(resp.data);
      showToast("Data kalender & sinyal berhasil diperbarui!");
    }
  } catch (err) {
    showToast("Gagal memperbarui: " + err, true);
  } finally {
    setTimeout(() => { btn.style.transform = "none"; }, 500);
  }
}

// Send signal to Discord Webhook with stage selection
async function handleSendDiscord() {
  const btn = document.getElementById("btn-send-discord");
  const stageSelect = document.getElementById("select-discord-stage");
  const stage = stageSelect ? stageSelect.value : "pre_news";
  
  const originalText = btn.innerHTML;
  btn.innerHTML = `<span>⏳ Mengirim ke Discord (@everyone)...</span>`;
  btn.disabled = true;
  
  try {
    const res = await fetch("/api/trigger-discord", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: stage })
    });
    const result = await res.json();
    
    if (result.success) {
      showToast("Sinyal & ping @everyone berhasil terkirim ke Discord!");
    } else {
      showToast("Gagal kirim: " + (result.error || "Periksa Webhook URL"), true);
    }
  } catch (err) {
    showToast("Kesalahan jaringan: " + err, true);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// Settings Modal Management
async function openSettingsModal() {
  const modal = document.getElementById("settings-modal");
  if (!modal) return;
  modal.classList.add("active");
  
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const s = await res.json();
      document.getElementById("setting-discord-url").value = s.discord_webhook_url || "";
      document.getElementById("setting-ai-model").value = s.ai_model || "google/gemini-2.5-flash";
      const hintEl = document.getElementById("setting-ai-key-hint");
      if (hintEl && s.ai_api_key_masked) {
        hintEl.textContent = `API Key saat ini: ${s.ai_api_key_masked} (Kosongkan jika tidak ingin mengubah)`;
      }
    }
  } catch (e) {
    console.error("Gagal membaca pengaturan:", e);
  }
}

function closeSettingsModal() {
  const modal = document.getElementById("settings-modal");
  if (modal) modal.classList.remove("active");
}

async function handleSaveSettings() {
  const webhookUrl = document.getElementById("setting-discord-url").value;
  const apiKey = document.getElementById("setting-ai-key").value;
  const model = document.getElementById("setting-ai-model").value;
  
  const saveBtn = document.getElementById("btn-save-settings");
  saveBtn.textContent = "Menyimpan...";
  saveBtn.disabled = true;
  
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        discord_webhook_url: webhookUrl,
        ai_api_key: apiKey,
        ai_model: model
      })
    });
    const result = await res.json();
    if (result.status === "success") {
      showToast("Pengaturan berhasil disimpan!");
      closeSettingsModal();
    } else {
      showToast("Gagal menyimpan: " + (result.message || "Unknown error"), true);
    }
  } catch (err) {
    showToast("Error jaringan saat menyimpan pengaturan", true);
  } finally {
    saveBtn.textContent = "Simpan Pengaturan";
    saveBtn.disabled = false;
  }
}

// Second-by-second local ticker
setInterval(() => {
  if (secondsRemaining > 0) {
    secondsRemaining -= 1;
    updateCountdownBoxes(secondsRemaining);
  }
  updateClocks();
}, 1000);

// Auto-sync state every 20 seconds
setInterval(() => {
  fetchState(false);
}, 20000);

// Setup Event Listeners on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  updateClocks();
  
  document.getElementById("btn-refresh").addEventListener("click", handleRefresh);
  document.getElementById("btn-send-discord").addEventListener("click", handleSendDiscord);
  
  document.getElementById("btn-open-settings").addEventListener("click", openSettingsModal);
  document.getElementById("btn-close-settings").addEventListener("click", closeSettingsModal);
  document.getElementById("btn-cancel-settings").addEventListener("click", closeSettingsModal);
  document.getElementById("btn-save-settings").addEventListener("click", handleSaveSettings);
  
  // Close modal when clicking outside
  document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target.id === "settings-modal") closeSettingsModal();
  });
  
  // Initial load
  fetchState(true);
});
