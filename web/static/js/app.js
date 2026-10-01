// ==========================================================================
// EANews Pro Terminal - Frontend Engine Logic (v3.2)
// ==========================================================================

let state = null;
let secondsRemaining = 0;

// Countdown parts helper
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

// Toast notification
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
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// Live Dual Clocks
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

  // UTC (London)
  const utcHours = String(now.getUTCHours()).padStart(2, '0');
  const utcMinutes = String(now.getUTCMinutes()).padStart(2, '0');
  const utcSeconds = String(now.getUTCSeconds()).padStart(2, '0');
  const clockUtcEl = document.getElementById("clock-utc");
  if (clockUtcEl) clockUtcEl.textContent = `${utcHours}:${utcMinutes}:${utcSeconds} UTC`;
}

// Main UI updater
function updateUI(data) {
  state = data;
  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  const calendar = data.calendar || {};
  
  secondsRemaining = nextEvent.seconds_until || 0;
  
  // 1. Ticker Tape Updates
  const tickerSchedule = document.getElementById("ticker-schedule");
  const tickerSpike = document.getElementById("ticker-spike");
  if (tickerSchedule && nextEvent.datetime_wib) {
    tickerSchedule.textContent = nextEvent.datetime_wib;
  }
  if (tickerSpike && signal.spike_potential) {
    tickerSpike.textContent = `${signal.spike_potential}% (${signal.spike_potential >= 90 ? 'Ekstrem' : 'Tinggi'})`;
  }

  // 2. 24-Hour Pre-News Radar Banner
  const radarBanner = document.getElementById("radar-banner");
  const radarCountdownVal = document.getElementById("radar-countdown-val");
  const radarEventName = document.getElementById("radar-event-name");
  const radarEventScheduleText = document.getElementById("radar-event-schedule-text");
  
  if (radarBanner) {
    // Show radar banner if event is within 36 hours (129,600s)
    if (secondsRemaining > 0 && secondsRemaining <= 129600) {
      radarBanner.style.display = "block";
    }
  }
  if (radarEventName) {
    radarEventName.textContent = nextEvent.group_name || "High Impact USD Release";
  }
  if (radarEventScheduleText) {
    radarEventScheduleText.textContent = nextEvent.datetime_wib 
      ? `${nextEvent.datetime_wib} (12:30 UTC)` 
      : "Jadwal resmi terkonfirmasi";
  }
  updateCountdownDigits(secondsRemaining);

  // 3. Hero Bias Card
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
  
  const contextPct = signal.context_percent || 80;
  contextEl.textContent = `${contextPct}%`;
  contextBar.style.width = `${contextPct}%`;
  
  const score = signal.xau_score || 0.0;
  scoreEl.textContent = score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  
  // Center-split score bar (-10.0 to +10.0 mapped to 5% - 95%)
  const scorePct = Math.max(5, Math.min(95, ((score + 10.0) / 20.0) * 100));
  scoreBar.style.width = `${scorePct}%`;
  
  if (engineModeTag && signal.analysis_mode) {
    engineModeTag.textContent = signal.analysis_mode.toUpperCase().replace("LLM_", "AI ");
  }

  // 4. Primary Event Focus Card
  const newsTitleEl = document.getElementById("next-news-title");
  const scheduleEl = document.getElementById("next-news-schedule");
  const itemsContainer = document.getElementById("news-items-list");
  
  newsTitleEl.textContent = nextEvent.group_name || "High Impact USD News";
  if (scheduleEl) {
    scheduleEl.textContent = nextEvent.datetime_wib ? nextEvent.datetime_wib : "Jadwal Resmi Sedang Dikonfirmasi";
  }
  
  itemsContainer.innerHTML = "";
  if (nextEvent.items && nextEvent.items.length > 0) {
    nextEvent.items.forEach(it => {
      const row = document.createElement("div");
      row.className = "breakdown-item";
      
      const figures = it.actual 
        ? `A: ${it.actual} · F: ${it.forecast} · P: ${it.previous}`
        : `F: ${it.forecast} · P: ${it.previous}`;
        
      row.innerHTML = `
        <span class="item-name">${it.title}</span>
        <span class="item-figures">${figures}</span>
      `;
      itemsContainer.appendChild(row);
    });
  } else {
    itemsContainer.innerHTML = `<div class="breakdown-item"><span class="item-name">Menunggu rilis data konsensus...</span></div>`;
  }

  // 5. Quant Metrics Trio
  const spikeValEl = document.getElementById("spike-value");
  const spikeBar = document.getElementById("spike-bar");
  const spikeTierBadge = document.getElementById("spike-tier-badge");
  const spike = signal.spike_potential || 90;
  
  spikeValEl.textContent = `${spike}%`;
  spikeBar.style.width = `${spike}%`;
  if (spikeTierBadge) {
    spikeTierBadge.textContent = spike >= 90 ? "EXTREME" : (spike >= 80 ? "VERY HIGH" : "HIGH");
  }
  
  const onewayValEl = document.getElementById("oneway-value");
  const onewayBar = document.getElementById("oneway-bar");
  const oneway = signal.one_way || 70;
  onewayValEl.textContent = `${oneway}%`;
  onewayBar.style.width = `${oneway}%`;
  
  const twowayValEl = document.getElementById("twoway-value");
  const twowayBar = document.getElementById("twoway-bar");
  const twoway = signal.two_way || 30;
  twowayValEl.textContent = `${twoway}%`;
  twowayBar.style.width = `${twoway}%`;

  // 6. Fundamental Dossier: Alasan Bias & Interpretasi Pasar (NFP / CPI / FOMC)
  renderFundamentalDossier(data);

  // 7. Correlated Lead-In Indicators
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
        const row = document.createElement("div");
        row.className = "correlated-row";
        
        const impactClass = item.impact_type === "buy" ? "impact-buy" : (item.impact_type === "sell" ? "impact-sell" : "impact-neutral");
        const impactIcon = item.impact_type === "buy" ? "🟢" : (item.impact_type === "sell" ? "🔴" : "🟡");
        
        row.innerHTML = `
          <div class="corr-top">
            <span class="corr-title">${item.title}</span>
            <span class="corr-tag">${item.category}</span>
          </div>
          ${item.latest_data ? `<div class="corr-data-line font-mono">📊 ${item.latest_data} · ${item.status || ''}</div>` : ''}
          <div class="corr-note">${item.relation_note}</div>
          <div class="corr-bottom">
            <span class="impact-text ${impactClass}">${impactIcon} ${item.bias_impact}</span>
            <span class="importance-badge font-mono">${item.importance}</span>
          </div>
        `;
        correlatedContainer.appendChild(row);
      });
    }
  }

  // 7. Full Economic Calendar (Tab 2)
  const fullCalendarList = document.getElementById("upcoming-calendar-list");
  if (fullCalendarList && calendar.upcoming_events) {
    const upcomingEvents = calendar.upcoming_events;
    if (upcomingEvents.length > 0) {
      fullCalendarList.innerHTML = "";
      upcomingEvents.forEach((ev, idx) => {
        const row = document.createElement("div");
        const is24h = ev.seconds_until > 0 && ev.seconds_until <= 86400;
        row.className = "calendar-row-card" + (is24h ? " highlight-24h" : "");
        
        const figures = ev.items && ev.items.length > 0 && ev.items[0].forecast !== "-"
          ? `F: ${ev.items[0].forecast} | P: ${ev.items[0].previous}`
          : "Konsensus Sedang Diperbarui";
          
        row.innerHTML = `
          <div class="col-event-name">
            <span class="ev-name-title">${ev.group_name}</span>
            <span class="status-chip chip-red" style="width: fit-content;">HIGH IMPACT</span>
          </div>
          <div class="col-schedule font-mono">
            <span class="ev-date-str">📅 ${ev.datetime_wib || ev.datetime}</span>
            <span class="ev-countdown-str">⏳ ${ev.countdown_str || ''}</span>
          </div>
          <div class="col-figures font-mono">
            <span>📊 ${figures}</span>
          </div>
          <div class="col-status-badge">
            ${is24h ? '<span class="badge-24h">⚡ SIAGA 24H</span>' : '<span class="status-chip chip-cyan">MENDATANG</span>'}
          </div>
        `;
        fullCalendarList.appendChild(row);
      });
    } else {
      fullCalendarList.innerHTML = `<div class="table-loading-row">Tidak ada event berita High Impact mendatang minggu ini.</div>`;
    }
  }

  // 8. Geopolitical AI Synthesis & Headlines
  const geoTagEl = document.getElementById("geo-sentiment-tag");
  const reasoningEl = document.getElementById("ai-reasoning");
  const geoSentiment = signal.geo_sentiment || "neutral";
  
  if (geoTagEl) {
    geoTagEl.className = `status-chip ${geoSentiment === 'bullish' ? 'chip-cyan' : (geoSentiment === 'bearish' ? 'chip-red' : 'chip-amber')}`;
    geoTagEl.textContent = `GEOPOLITIK: ${geoSentiment.toUpperCase()}`;
  }
  if (reasoningEl) {
    reasoningEl.textContent = signal.ai_reasoning || "Analisis geopolitik dan deviasi fundamental sedang aktif.";
  }

  const newsFeedContainer = document.getElementById("geopolitical-news-container");
  if (newsFeedContainer && data.news) {
    newsFeedContainer.innerHTML = "";
    data.news.slice(0, 5).forEach(news => {
      const item = document.createElement("div");
      item.className = "wire-item";
      
      const impact = news.impact_xau || "NEUTRAL";
      const impactClass = impact.includes("BUY") ? "chip-cyan" : (impact.includes("SELL") ? "chip-red" : "chip-amber");
      
      item.innerHTML = `
        <div class="wire-item-head">
          <span class="wire-headline">${news.title}</span>
          <span class="status-chip ${impactClass}">${impact}</span>
        </div>
        ${news.impact_note ? `<div class="news-ai-note">💡 ${news.impact_note}</div>` : ''}
        <div class="wire-foot">
          <span class="font-mono">${news.source || 'Wire'}</span>
          <span class="font-mono">${news.published || 'Terbaru'}</span>
        </div>
      `;
      newsFeedContainer.appendChild(item);
    });
  }

  // 9. Sync indicator text
  const syncText = document.getElementById("sync-status-text");
  if (syncText) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    syncText.textContent = `LIVE (${timeStr} WIB)`;
  }
}

// Render dedicated fundamental dossier (Reason, Transmission, Deviation rules, Watch points)
function renderFundamentalDossier(data) {
  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  const dossier = signal.fundamental_dossier || {};
  const groupName = nextEvent.group_name || "HIGH IMPACT USD";
  const bias = signal.expected_bias || "XAU NEUTRAL";
  const isBuy = bias.includes("BUY");
  const isSell = bias.includes("SELL");

  const dossierCard = document.getElementById("card-fundamental-dossier");
  if (!dossierCard) return;

  dossierCard.classList.remove("buy", "sell");
  if (isBuy) dossierCard.classList.add("buy");
  if (isSell) dossierCard.classList.add("sell");

  // Badges & Headers
  const eventBadge = document.getElementById("dossier-event-badge");
  const eventNameTag = document.getElementById("dossier-event-name-tag");
  const dossierTitle = document.getElementById("dossier-title");
  const dossierHeadline = document.getElementById("dossier-headline");
  const biasPill = document.getElementById("dossier-bias-indicator");
  const biasText = document.getElementById("dossier-bias-text");

  if (eventBadge) eventBadge.textContent = dossier.event_badge || "🔴 TIER-1 ULTRA HIGH IMPACT";
  if (eventNameTag) eventNameTag.textContent = `${groupName.toUpperCase()} DOSSIER`;
  if (dossierTitle) dossierTitle.textContent = `Alasan Bias & Interpretasi Fundamental ${groupName}`;
  if (dossierHeadline) {
    dossierHeadline.textContent = dossier.headline_summary || `Laporan transmisi makroekonomi dan respon deviasi konsensus rilis ${groupName}.`;
  }

  if (biasPill && biasText) {
    biasPill.className = `dossier-bias-pill ${isSell ? 'pill-sell' : ''}`;
    biasText.textContent = `BIAS: ${bias}`;
  }

  // 1. Why Bias Reason
  const whyReasonEl = document.getElementById("dossier-why-reason");
  if (whyReasonEl) {
    const rawReason = signal.why_bias_reason || dossier.why_bias_reason;
    if (rawReason) {
      whyReasonEl.textContent = rawReason;
    } else {
      whyReasonEl.textContent = "Sedang mengkalkulasi komparasi data konsensus...";
    }
  }

  // 2. Market Transmission
  const transmissionBody = document.getElementById("dossier-transmission-body");
  if (transmissionBody) {
    const rawTransmission = signal.market_interpretation || dossier.market_interpretation || "";
    if (rawTransmission) {
      const lines = rawTransmission.split("\n").filter(l => l.trim().length > 0);
      let html = "";
      lines.forEach(line => {
        let formatted = line;
        if (line.includes(":")) {
          const colonIdx = line.indexOf(":");
          const prefix = line.substring(0, colonIdx);
          const rest = line.substring(colonIdx + 1);
          formatted = `<strong>${prefix}:</strong>${rest}`;
        }
        html += `<div class="transmission-step-item"><p class="dossier-text">${formatted}</p></div>`;
      });
      transmissionBody.innerHTML = html;
    } else {
      transmissionBody.innerHTML = `<p class="dossier-text">Mekanisme transmisi data ke DXY, Yield US 10Y, dan Emas sedang dianalisis.</p>`;
    }
  }

  // 3. Consensus Rules Matrix (Deviation Scenarios)
  const rulesGrid = document.getElementById("dossier-rules-grid");
  const rules = signal.consensus_rules || dossier.consensus_rules || [];
  if (rulesGrid && rules.length > 0) {
    rulesGrid.innerHTML = "";
    rules.forEach(r => {
      const isBullish = r.condition.toLowerCase().includes("bullish") || r.condition.toLowerCase().includes("dovish");
      const isBearish = r.condition.toLowerCase().includes("bearish") || r.condition.toLowerCase().includes("hawkish");
      const cardClass = isBullish ? "card-bullish" : (isBearish ? "card-bearish" : "card-mixed");

      const card = document.createElement("div");
      card.className = `rule-scenario-card ${cardClass}`;
      card.innerHTML = `
        <div class="rule-cond-tag">${r.condition}</div>
        <div class="rule-trigger-box">🎯 <strong>Pemicu:</strong> ${r.trigger}</div>
        <div class="rule-detail-line"><strong>DXY & Yields:</strong> ${r.dxy_yield_reaction}</div>
        <div class="rule-reaction-badge">${r.xau_reaction}</div>
        <div class="rule-meta-foot">
          <span class="rule-pips font-mono">⚡ ${r.expected_pips}</span>
          <span class="rule-action-pill">${r.action}</span>
        </div>
      `;
      rulesGrid.appendChild(card);
    });
  }

  // 4. Key Watch Factors
  const watchFactorsContainer = document.getElementById("dossier-watch-factors");
  const factors = signal.key_watch_factors || dossier.key_watch_factors || [];
  if (watchFactorsContainer && factors.length > 0) {
    watchFactorsContainer.innerHTML = "";
    factors.forEach(f => {
      const item = document.createElement("div");
      item.className = "watch-factor-item";
      item.innerHTML = `
        <div>
          <span class="wf-name">${f.factor}</span>
          <span class="wf-importance"> · ${f.importance}</span>
        </div>
        <span class="wf-bench font-mono">${f.benchmark}</span>
      `;
      watchFactorsContainer.appendChild(item);
    });
  }

  // 5. Tactical Guidance
  const tacticalEl = document.getElementById("dossier-tactical-guidance");
  if (tacticalEl) {
    tacticalEl.textContent = signal.tactical_guidance || dossier.tactical_guidance || "Pasang SL minimal 40-60 pips sebelum rilis untuk mengantisipasi pelebaran spread broker.";
  }

  // 6. Also sync Tab 4 Playbook dynamically
  const playbookTitle = document.getElementById("playbook-tab-title");
  if (playbookTitle) {
    playbookTitle.textContent = `Panduan 3 Skenario Reaksi Pasar Menjelang & Saat Rilis ${groupName}`;
  }
}

// Update the 4 digital clock segments and radar countdown
function updateCountdownDigits(sec) {
  const parts = getCountdownParts(sec);
  
  const daysEl = document.getElementById("cd-days");
  const hoursEl = document.getElementById("cd-hours");
  const minEl = document.getElementById("cd-minutes");
  const secEl = document.getElementById("cd-seconds");
  
  if (daysEl) daysEl.textContent = padZero(parts.days);
  if (hoursEl) hoursEl.textContent = padZero(parts.hours);
  if (minEl) minEl.textContent = padZero(parts.minutes);
  if (secEl) secEl.textContent = padZero(parts.seconds);

  const radarVal = document.getElementById("radar-countdown-val");
  if (radarVal) {
    if (sec > 0) {
      if (parts.days > 0) {
        radarVal.textContent = `${parts.days} hari ${parts.hours} jam ${parts.minutes} menit`;
      } else {
        radarVal.textContent = `${parts.hours} jam ${parts.minutes} menit ${parts.seconds} detik`;
      }
    } else {
      radarVal.textContent = "Data Telah Dirilis (Released)";
    }
  }
}

// Fetch live state from API
async function fetchState(force = false) {
  try {
    const res = await fetch(`/api/state?force=${force}&t=${Date.now()}`);
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
  showToast("Menghubungkan kalender & menyinkronkan data...");
  
  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    if (res.ok) {
      const resp = await res.json();
      updateUI(resp.data);
      showToast("Data kalender & sinyal berhasil disinkronkan!");
    }
  } catch (err) {
    showToast("Gagal memperbarui: " + err, true);
  } finally {
    setTimeout(() => { btn.style.transform = "none"; }, 500);
  }
}

// Execute Discord Dispatch
async function handleSendDiscord() {
  const btn = document.getElementById("btn-send-discord");
  const stageSelect = document.getElementById("select-discord-stage");
  const stage = stageSelect ? stageSelect.value : "pre_news";
  
  const originalHtml = btn.innerHTML;
  btn.innerHTML = `<span>⏳ Mengirim sinyal...</span>`;
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
      showToast("Gagal: " + (result.error || "Periksa Webhook URL di Pengaturan"), true);
    }
  } catch (err) {
    showToast("Kesalahan jaringan: " + err, true);
  } finally {
    btn.innerHTML = originalHtml;
    btn.disabled = false;
  }
}

// Tab Switching
function setupTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      
      tabBtns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      tabPanels.forEach(p => p.classList.remove("active"));
      
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

// Settings Modal Management
async function openSettingsModal() {
  const modal = document.getElementById("settings-modal");
  if (!modal) return;
  modal.classList.add("active");
  
  try {
    const res = await fetch(`/api/settings?t=${Date.now()}`);
    if (res.ok) {
      const s = await res.json();
      document.getElementById("setting-discord-url").value = s.discord_webhook_url || "";
      document.getElementById("setting-ai-model").value = s.ai_model || "google/gemini-2.5-flash";
      const hintEl = document.getElementById("setting-ai-key-hint");
      if (hintEl && s.ai_api_key_masked) {
        hintEl.textContent = `API Key saat ini: ${s.ai_api_key_masked} (Kosongkan jika tidak diubah)`;
      }
    }
  } catch (e) {
    console.error("Gagal membaca settings:", e);
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
      showToast("Gagal: " + (result.message || "Unknown error"), true);
    }
  } catch (err) {
    showToast("Error jaringan saat menyimpan", true);
  } finally {
    saveBtn.textContent = "Simpan Perubahan";
    saveBtn.disabled = false;
  }
}

// Real-time second countdown ticker
setInterval(() => {
  if (secondsRemaining > 0) {
    secondsRemaining -= 1;
    updateCountdownDigits(secondsRemaining);
  }
  updateClocks();
}, 1000);

// Auto-sync polling every 20 seconds
setInterval(() => {
  fetchState(false);
}, 20000);

// Initial Load & Event Binding
document.addEventListener("DOMContentLoaded", () => {
  updateClocks();
  setupTabs();
  
  document.getElementById("btn-refresh").addEventListener("click", handleRefresh);
  document.getElementById("btn-send-discord").addEventListener("click", handleSendDiscord);
  
  document.getElementById("btn-open-settings").addEventListener("click", openSettingsModal);
  document.getElementById("btn-close-settings").addEventListener("click", closeSettingsModal);
  document.getElementById("btn-cancel-settings").addEventListener("click", closeSettingsModal);
  document.getElementById("btn-save-settings").addEventListener("click", handleSaveSettings);
  
  // Close modal when clicking backdrop
  document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target.id === "settings-modal") closeSettingsModal();
  });
  
  // Initial data load
  fetchState(true);
});
