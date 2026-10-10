// ==========================================================================
// EANews Pro Terminal - Frontend Engine Logic (v5.0 Institutional Edition)
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

// Toast notification with sleek vector glyphs
function showToast(message, isError = false) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  
  const toast = document.createElement("div");
  toast.className = `toast ${isError ? 'toast-error' : 'toast-success'}`;
  
  const iconSvg = isError
    ? `<svg class="toast-svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
    : `<svg class="toast-svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
    
  toast.innerHTML = `<span class="toast-icon-wrap">${iconSvg}</span> <span class="toast-msg">${message}</span>`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// Live Dual Clocks (Financial Hubs)
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

let lastSeenTopNewsTitle = "";

// Dynamic Continuous Marquee Ticker
function updateTicker(data) {
  const tickerContent = document.getElementById("ticker-content");
  const tickerClone = document.getElementById("ticker-content-clone");
  const tickerBar = document.getElementById("ticker-bar");
  if (!tickerContent) return;

  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  const newsList = data.news || [];
  
  const bias = signal.expected_bias || "XAU NEUTRAL";
  const score = signal.xau_score || 0.0;
  const spike = signal.spike_potential || 90;
  const groupName = nextEvent.group_name || "High Impact USD";
  const scheduleStr = nextEvent.datetime_wib || "Jadwal resmi";
  const geoSentiment = signal.geo_sentiment ? signal.geo_sentiment.toUpperCase() : "DEFENSIVE";

  // Detect if new geopolitical news arrived
  const topNewsTitle = newsList.length > 0 ? newsList[0].title : "";
  let isNewNews = false;
  if (topNewsTitle && topNewsTitle !== lastSeenTopNewsTitle) {
    if (lastSeenTopNewsTitle !== "") {
      isNewNews = true;
      if (tickerBar) {
        tickerBar.classList.add("ticker-flash-new");
        setTimeout(() => tickerBar.classList.remove("ticker-flash-new"), 4000);
      }
      showToast(`Berita Geopolitik Baru: ${topNewsTitle.substring(0, 50)}...`);
    }
    lastSeenTopNewsTitle = topNewsTitle;
  }

  // Construct items
  const biasColor = bias.includes("BUY") ? "cyan-text" : (bias.includes("SELL") ? "red-text" : "gold-text");
  
  let html = `
    <span class="ticker-item">
      <span class="ticker-tag-chip chip-breaking">SIGNAL</span>
      <strong class="${biasColor}">XAU/USD: ${bias}</strong> <span class="font-mono">(${score > 0 ? '+' : ''}${score.toFixed(2)})</span>
    </span>
    <span class="ticker-bullet">•</span>
    <span class="ticker-item">
      <span class="ticker-tag-chip chip-event">RADAR</span>
      <strong class="gold-text">${groupName}:</strong> <span>${scheduleStr}</span>
    </span>
    <span class="ticker-bullet">•</span>
    <span class="ticker-item">
      <strong class="red-text">SPIKE VOLATILITY:</strong> <span class="font-mono">${spike}% (${spike >= 90 ? 'Ekstrem' : 'Tinggi'})</span>
    </span>
    <span class="ticker-bullet">•</span>
    <span class="ticker-item">
      <span class="ticker-tag-chip chip-geo">GEOPOLITIK</span>
      <strong class="cyan-text">${geoSentiment}</strong>
    </span>
    <span class="ticker-bullet">•</span>
  `;

  // Append Top Geopolitical News
  if (newsList.length > 0) {
    newsList.slice(0, 6).forEach((n, idx) => {
      const isTopBreaking = idx === 0 && isNewNews;
      const chipBadge = isTopBreaking 
        ? '<span class="ticker-tag-chip chip-breaking">BARU</span>' 
        : '<span class="ticker-tag-chip chip-geo">WIRE</span>';
      const impactClass = n.impact_xau && n.impact_xau.includes("BUY") ? "cyan-text" : (n.impact_xau && n.impact_xau.includes("SELL") ? "red-text" : "gold-text");
      const impactTag = n.impact_xau ? `<strong class="${impactClass}">[${n.impact_xau}]</strong> ` : "";

      html += `
        <span class="ticker-item">
          ${chipBadge}
          <span>${n.title} ${impactTag}</span>
        </span>
        <span class="ticker-bullet">•</span>
      `;
    });
  }

  tickerContent.innerHTML = html;
  if (tickerClone) {
    tickerClone.innerHTML = html;
  }
}

// Main UI updater
function updateUI(data) {
  state = data;
  const signal = data.signal || {};
  const nextEvent = data.next_event || {};
  const calendar = data.calendar || {};
  
  secondsRemaining = nextEvent.seconds_until || 0;
  
  // 1. Ticker
  updateTicker(data);

  // 2. 24-Hour Pre-News Radar Banner
  const radarBanner = document.getElementById("radar-banner");
  const radarCountdownVal = document.getElementById("radar-countdown-val");
  const radarEventName = document.getElementById("radar-event-name");
  const radarEventScheduleText = document.getElementById("radar-event-schedule-text");
  
  if (radarBanner) {
    const statusTextEl = radarBanner.querySelector(".radar-status-text");
    if (statusTextEl) {
      if (secondsRemaining <= 86400 && secondsRemaining > 0) {
        statusTextEl.textContent = "SIAGA 24 JAM PRA-RILIS BERITA AKTIF";
      } else if (secondsRemaining > 86400) {
        const days = Math.ceil(secondsRemaining / 86400);
        statusTextEl.textContent = `RADAR BERITA MENDATANG (${days} HARI LAGI)`;
      } else {
        statusTextEl.textContent = "DATA TELAH DIRILIS (POST-EVENT)";
      }
    }
  }
  if (radarEventName) {
    radarEventName.textContent = nextEvent.group_name || "High Impact USD Release";
  }
  if (radarEventScheduleText) {
    radarEventScheduleText.textContent = nextEvent.datetime_wib || "Jadwal resmi terkonfirmasi";
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
    symbolEl.innerHTML = `
      <svg class="bias-glyph-icon glyph-sell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 7l10 10"/>
        <path d="M17 7v10H7"/>
      </svg>`;
  } else if (bias.includes("BUY")) {
    biasCard.classList.add("buy");
    symbolEl.innerHTML = `
      <svg class="bias-glyph-icon glyph-buy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 17L17 7"/>
        <path d="M7 7h10v10"/>
      </svg>`;
  } else {
    symbolEl.innerHTML = `
      <svg class="bias-glyph-icon glyph-neutral" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>`;
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
        <span class="item-figures font-mono">${figures}</span>
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
        const impactDot = `<span class="impact-indicator-dot ${item.impact_type || 'neutral'}"></span>`;
        
        row.innerHTML = `
          <div class="corr-top">
            <span class="corr-title">${item.title}</span>
            <span class="corr-tag font-mono">${item.category}</span>
          </div>
          ${item.latest_data ? `<div class="corr-data-line font-mono"><span class="data-tag">DATA:</span> ${item.latest_data} · ${item.status || ''}</div>` : ''}
          <div class="corr-note">${item.relation_note}</div>
          <div class="corr-bottom">
            <span class="impact-text ${impactClass}">${impactDot} ${item.bias_impact}</span>
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
      upcomingEvents.forEach((ev) => {
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
            <span class="ev-date-str">${ev.datetime_wib || ev.datetime}</span>
            <span class="ev-countdown-str font-mono">${ev.countdown_str || ''}</span>
          </div>
          <div class="col-figures font-mono">
            <span>${figures}</span>
          </div>
          <div class="col-status-badge">
            ${is24h ? '<span class="badge-24h">SIAGA 24H</span>' : '<span class="status-chip chip-cyan">MENDATANG</span>'}
          </div>
        `;
        fullCalendarList.appendChild(row);
      });
    } else {
      fullCalendarList.innerHTML = `<div class="table-loading-row font-mono">Tidak ada event berita High Impact mendatang minggu ini.</div>`;
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
        ${news.impact_note ? `<div class="news-ai-note font-mono">${news.impact_note}</div>` : ''}
        <div class="wire-foot">
          <span class="font-mono">${news.source || 'Wire'}</span>
          <span class="font-mono">${news.published || 'Terbaru'}</span>
        </div>
      `;
      newsFeedContainer.appendChild(item);
    });
  }

  // 9. Daily Macro Bulletins (JA Journal Ars Feed)
  if (data.daily_bulletins) {
    renderDailyBulletins(data.daily_bulletins);
  }

  // 10. Sync indicator text
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

  if (eventBadge) eventBadge.textContent = dossier.event_badge || "TIER-1 ULTRA HIGH IMPACT";
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
      lines.forEach((line, idx) => {
        let formatted = line;
        if (line.includes(":")) {
          const colonIdx = line.indexOf(":");
          const prefix = line.substring(0, colonIdx);
          const rest = line.substring(colonIdx + 1);
          formatted = `<strong>${prefix}:</strong>${rest}`;
        }
        html += `
          <div class="transmission-step-item">
            <span class="step-num-bullet">${idx + 1}</span>
            <p class="dossier-text">${formatted}</p>
          </div>`;
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
        <div class="rule-cond-tag font-mono">${r.condition}</div>
        <div class="rule-trigger-box"><span class="trigger-label font-mono">PEMICU:</span> ${r.trigger}</div>
        <div class="rule-detail-line"><strong>DXY & Yields:</strong> ${r.dxy_yield_reaction}</div>
        <div class="rule-reaction-badge">${r.xau_reaction}</div>
        <div class="rule-meta-foot">
          <span class="rule-pips font-mono">${r.expected_pips}</span>
          <span class="rule-action-pill font-mono">${r.action}</span>
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
  const playbookTabBtn = document.getElementById("tab-playbook-title");
  if (playbookTabBtn) {
    playbookTabBtn.textContent = `Skenario Trading ${groupName}`;
  }

  const playbookGrid = document.getElementById("playbook-scenarios-grid");
  if (playbookGrid && rules.length > 0) {
    playbookGrid.innerHTML = "";
    rules.forEach((r, idx) => {
      const isBullish = r.condition.toLowerCase().includes("bullish") || r.condition.toLowerCase().includes("dovish");
      const isBearish = r.condition.toLowerCase().includes("bearish") || r.condition.toLowerCase().includes("hawkish");
      const cardClass = isBullish ? "card-bullish" : (isBearish ? "card-bearish" : "card-mixed");
      const impactText = isBullish ? "BULLISH XAU (BUY)" : (isBearish ? "BEARISH XAU (SELL)" : "TWO-WAY SPIKE");

      const card = document.createElement("div");
      card.className = `scenario-card ${cardClass}`;
      card.innerHTML = `
        <div class="scenario-header">
          <span class="scenario-badge font-mono">SKENARIO ${idx + 1}: ${r.condition.toUpperCase()}</span>
          <span class="scenario-impact font-mono">${impactText}</span>
        </div>
        <div class="scenario-trigger">
          <strong>Kondisi:</strong> ${r.trigger}
        </div>
        <p class="scenario-desc">${r.dxy_yield_reaction}. ${r.xau_reaction}.</p>
        <div class="scenario-action">
          <span><strong>Rekomendasi Arah:</strong> ${r.action}</span>
          <span><strong>Target Spike:</strong> ${r.expected_pips}</span>
        </div>
      `;
      playbookGrid.appendChild(card);
    });
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
        radarVal.textContent = `${parts.days}d ${padZero(parts.hours)}h ${padZero(parts.minutes)}m ${padZero(parts.seconds)}s`;
      } else {
        radarVal.textContent = `${padZero(parts.hours)}h ${padZero(parts.minutes)}m ${padZero(parts.seconds)}s`;
      }
    } else {
      radarVal.textContent = "Data Telah Dirilis";
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
  btn.classList.add("rotating");
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
    setTimeout(() => { btn.classList.remove("rotating"); }, 600);
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
      document.getElementById("setting-ai-model").value = s.ai_model || "gemini-3.8-flash";
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

// ==========================================================================
// DAILY MACRO BULLETINS & AI INTERPRETATION ENGINE (JA JOURNAL ARS)
// ==========================================================================
let currentBulletins = [];
let activeNewsCategory = "all";

function renderDailyBulletins(bulletins) {
  if (bulletins && bulletins.length > 0) {
    currentBulletins = bulletins;
  }
  const container = document.getElementById("daily-bulletin-feed");
  if (!container) return;

  const filtered = activeNewsCategory === "all"
    ? currentBulletins
    : currentBulletins.filter(b => (b.category || "").toLowerCase().includes(activeNewsCategory.toLowerCase()));

  if (!filtered || filtered.length === 0) {
    container.innerHTML = `<div class="table-loading-row font-mono">Tidak ada berita untuk filter kategori ini.</div>`;
    return;
  }

  container.innerHTML = "";
  filtered.forEach(item => {
    const interp = item.interpretation || {};
    const bias = interp.bias || "NEUTRAL";
    const biasBadge = interp.bias_badge || "ANALISIS PASAR";
    const colorClass = bias.includes("BUY") ? "chip-cyan" : (bias.includes("SELL") ? "chip-red" : "chip-gold");
    const borderClass = bias.includes("BUY") ? "border-buy" : (bias.includes("SELL") ? "border-sell" : "border-neutral");

    const card = document.createElement("article");
    card.className = `bulletin-card ${borderClass}`;
    card.id = `bulletin-${item.id}`;

    // Format paragraphs
    const paragraphsHtml = (item.paragraphs || [])
      .map(p => `<p class="bulletin-paragraph">${p}</p>`)
      .join("");

    // Intermarket matrix row
    const intermarket = interp.intermarket_matrix || {};
    let intermarketHtml = "";
    if (intermarket.oil || intermarket.yields || intermarket.dxy || intermarket.xau) {
      intermarketHtml = `
        <div class="intermarket-matrix-box">
          <span class="matrix-box-label font-mono">DAMPAK KOMODITAS &amp; PASAR GLOBAL:</span>
          <div class="matrix-pills-row">
            ${intermarket.oil ? `<div class="asset-pill"><span class="asset-k font-mono">MINYAK:</span> <span class="asset-v">${intermarket.oil}</span></div>` : ''}
            ${intermarket.yields ? `<div class="asset-pill"><span class="asset-k font-mono">US 10Y:</span> <span class="asset-v">${intermarket.yields}</span></div>` : ''}
            ${intermarket.dxy ? `<div class="asset-pill"><span class="asset-k font-mono">DXY:</span> <span class="asset-v">${intermarket.dxy}</span></div>` : ''}
            ${intermarket.xau ? `<div class="asset-pill asset-pill-highlight"><span class="asset-k font-mono">XAU/USD:</span> <span class="asset-v">${intermarket.xau}</span></div>` : ''}
          </div>
        </div>
      `;
    }

    // Macro transmission lines
    let transmissionHtml = "";
    if (interp.transmission_mechanism) {
      const transLines = interp.transmission_mechanism.split("\n").filter(l => l.trim().length > 0);
      transmissionHtml = `
        <div class="transmission-flow-box">
          <span class="flow-box-label font-mono">MEKANISME TRANSMISI MAKROEKONOMI:</span>
          <ul class="flow-points-list">
            ${transLines.map(line => `<li>${line}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="bulletin-header">
        <div class="bulletin-channel-tag">
          <div class="bulletin-avatar-mini font-mono">JA</div>
          <div class="bulletin-tag-info">
            <span class="bulletin-channel-name">${item.channel || "JA (Journal Ars)"}</span>
            <span class="bulletin-followers-sub font-mono">${item.channel_badge || "882 pengikut"}</span>
          </div>
        </div>
        <div class="bulletin-meta-right">
          <span class="status-chip chip-amber font-mono">${item.category || "Makro"}</span>
          <span class="bulletin-time-pill font-mono">${item.published_time || "Terbaru"}</span>
        </div>
      </div>

      <h3 class="bulletin-headline">${item.title}</h3>

      <div class="bulletin-body">
        ${paragraphsHtml}
      </div>

      <!-- KOTAK INTERPRETASI PASAR & XAU/USD -->
      <div class="bulletin-interpretation-card ${interp.impact_color || 'neutral'}">
        <div class="interpretation-top-row">
          <div class="interpretation-title-tag">
            <svg class="interp-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
            <span class="interp-header-label font-mono">INTERPRETASI PASAR &amp; XAU/USD</span>
          </div>
          <div class="interp-bias-cluster">
            <span class="status-chip ${colorClass} font-mono">${bias}</span>
            <span class="bias-sub-badge font-mono">${biasBadge}</span>
          </div>
        </div>

        ${interp.headline_analysis ? `
          <div class="interp-thesis-statement">
            <strong>Analisis Kunci:</strong> ${interp.headline_analysis}
          </div>
        ` : ''}

        ${transmissionHtml}

        ${intermarketHtml}

        ${interp.tactical_action ? `
          <div class="tactical-action-box">
            <span class="action-box-label font-mono">PANDUAN TAKTIS TRADER:</span>
            <p class="action-text">${interp.tactical_action}</p>
          </div>
        ` : ''}

        <div class="bulletin-actions-foot">
          <button class="btn-copy-bulletin font-mono" data-id="${item.id}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>SALIN BERITA &amp; INTERPRETASI</span>
          </button>
          <span class="foot-disclaimer font-mono">EANews Novaire Macro Desk</span>
        </div>
      </div>
    `;

    container.appendChild(card);
  });

  // Attach copy listeners
  container.querySelectorAll(".btn-copy-bulletin").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      copyBulletinToClipboard(id);
    });
  });
}

function copyBulletinToClipboard(id) {
  const item = currentBulletins.find(b => b.id === id);
  if (!item) return;

  const interp = item.interpretation || {};
  let text = `📢 ${item.channel || "JA (Journal Ars)"} • ${item.published_time || "Berita Harian"}\n\n`;
  text += `${item.title}\n\n`;
  (item.paragraphs || []).forEach(p => {
    text += `${p}\n\n`;
  });
  text += `━━━━━━━━━━━━━━━━━━━━━\n`;
  text += `📊 INTERPRETASI PASAR & XAU/USD\n`;
  text += `Arah/Bias: ${interp.bias || 'NEUTRAL'} (${interp.bias_badge || ''})\n\n`;
  if (interp.headline_analysis) {
    text += `💡 Analisis: ${interp.headline_analysis}\n\n`;
  }
  if (interp.transmission_mechanism) {
    text += `🔄 Transmisi Makro:\n${interp.transmission_mechanism}\n\n`;
  }
  if (interp.tactical_action) {
    text += `🎯 Panduan Taktis:\n${interp.tactical_action}\n`;
  }
  text += `━━━━━━━━━━━━━━━━━━━━━\nEANews Novaire AI Terminal`;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast("Berita & Interpretasi berhasil disalin ke clipboard!");
    }).catch(() => {
      showToast("Berhasil disalin ke clipboard!");
    });
  } else {
    showToast("Berhasil disalin ke clipboard!");
  }
}

function renderCustomInterpretationResult(interp, rawText) {
  const resultCard = document.getElementById("custom-interpret-result");
  if (!resultCard) return;

  const bias = interp.bias || "NEUTRAL";
  const biasBadge = interp.bias_badge || "ANALISIS TEKS";
  const colorClass = bias.includes("BUY") ? "chip-cyan" : (bias.includes("SELL") ? "chip-red" : "chip-gold");
  const intermarket = interp.intermarket_matrix || {};

  let transHtml = "";
  if (interp.transmission_mechanism) {
    const lines = interp.transmission_mechanism.split("\n").filter(l => l.trim().length > 0);
    transHtml = `
      <ul class="flow-points-list">
        ${lines.map(l => `<li>${l}</li>`).join("")}
      </ul>
    `;
  }

  resultCard.classList.remove("hidden");
  resultCard.innerHTML = `
    <div class="interpretation-top-row">
      <div class="interpretation-title-tag">
        <svg class="interp-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        <span class="interp-header-label font-mono">HASIL INTERPRETASI AI QUANT</span>
      </div>
      <div class="interp-bias-cluster">
        <span class="status-chip ${colorClass} font-mono">${bias}</span>
        <span class="bias-sub-badge font-mono">${biasBadge}</span>
      </div>
    </div>

    ${interp.headline_analysis ? `
      <div class="interp-thesis-statement">
        <strong>Ringkasan Eksekutif:</strong> ${interp.headline_analysis}
      </div>
    ` : ''}

    <div class="transmission-flow-box">
      <span class="flow-box-label font-mono">MEKANISME TRANSMISI PASAR (DXY • YIELD • XAU):</span>
      ${transHtml}
    </div>

    ${(intermarket.oil || intermarket.yields || intermarket.dxy || intermarket.xau) ? `
      <div class="intermarket-matrix-box">
        <span class="matrix-box-label font-mono">PROYEKSI DAMPAK ASET:</span>
        <div class="matrix-pills-row">
          ${intermarket.oil ? `<div class="asset-pill"><span class="asset-k font-mono">MINYAK:</span> <span class="asset-v">${intermarket.oil}</span></div>` : ''}
          ${intermarket.yields ? `<div class="asset-pill"><span class="asset-k font-mono">US 10Y:</span> <span class="asset-v">${intermarket.yields}</span></div>` : ''}
          ${intermarket.dxy ? `<div class="asset-pill"><span class="asset-k font-mono">DXY:</span> <span class="asset-v">${intermarket.dxy}</span></div>` : ''}
          ${intermarket.xau ? `<div class="asset-pill asset-pill-highlight"><span class="asset-k font-mono">XAU/USD:</span> <span class="asset-v">${intermarket.xau}</span></div>` : ''}
        </div>
      </div>
    ` : ''}

    ${interp.tactical_action ? `
      <div class="tactical-action-box">
        <span class="action-box-label font-mono">PANDUAN EKSEKUSI TRADING:</span>
        <p class="action-text">${interp.tactical_action}</p>
      </div>
    ` : ''}
  `;
}

async function runCustomNewsInterpretation() {
  const inputEl = document.getElementById("custom-news-input");
  const runBtn = document.getElementById("btn-run-interpret");
  if (!inputEl || !runBtn) return;

  const rawText = inputEl.value.trim();
  if (!rawText) {
    showToast("Silakan tempel teks berita terlebih dahulu.", true);
    return;
  }

  runBtn.disabled = true;
  runBtn.innerHTML = `<span>MENGANALISIS...</span>`;
  showToast("AI sedang menganalisis teks berita & menghitung transmisi makro...");

  try {
    const res = await fetch("/api/interpret-custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: rawText })
    });
    const data = await res.json();
    if (data.status === "success" && data.interpretation) {
      renderCustomInterpretationResult(data.interpretation, rawText);
      showToast("Interpretasi berita berhasil dibuat!");
    } else {
      showToast("Gagal menganalisis berita: " + (data.detail || "Error"), true);
    }
  } catch (err) {
    showToast("Error jaringan saat analisis: " + err, true);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      <span>INTERPRETASIKAN DENGAN AI</span>
    `;
  }
}

function setupDailyNewsEvents() {
  // Category Filter Pills
  const catPills = document.querySelectorAll("#news-category-filters .cat-pill");
  catPills.forEach(pill => {
    pill.addEventListener("click", () => {
      catPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeNewsCategory = pill.getAttribute("data-cat") || "all";
      renderDailyBulletins(currentBulletins);
    });
  });

  // Toggle Custom Interpreter
  const toggleBtn = document.getElementById("btn-toggle-custom-interpreter");
  const closeBtn = document.getElementById("btn-close-custom-interpreter");
  const interpreterPanel = document.getElementById("custom-interpreter-box");
  const runBtn = document.getElementById("btn-run-interpret");
  const clearBtn = document.getElementById("btn-clear-custom-input");

  if (toggleBtn && interpreterPanel) {
    toggleBtn.addEventListener("click", () => {
      interpreterPanel.classList.toggle("hidden");
      if (!interpreterPanel.classList.contains("hidden")) {
        const input = document.getElementById("custom-news-input");
        if (input) input.focus();
      }
    });
  }

  if (closeBtn && interpreterPanel) {
    closeBtn.addEventListener("click", () => {
      interpreterPanel.classList.add("hidden");
    });
  }

  if (runBtn) {
    runBtn.addEventListener("click", runCustomNewsInterpretation);
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      const input = document.getElementById("custom-news-input");
      if (input) input.value = "";
      const resultCard = document.getElementById("custom-interpret-result");
      if (resultCard) {
        resultCard.innerHTML = "";
        resultCard.classList.add("hidden");
      }
    });
  }

  // Jump from Tab 1 to Tab 3 Daily News
  const gotoNewsBtn = document.getElementById("btn-goto-daily-news");
  if (gotoNewsBtn) {
    gotoNewsBtn.addEventListener("click", () => {
      const newsTabBtn = document.querySelector('.tab-btn[data-tab="tab-intelligence"]');
      if (newsTabBtn) newsTabBtn.click();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
}

// Initial Load & Event Binding
document.addEventListener("DOMContentLoaded", () => {
  updateClocks();
  setupTabs();
  setupDailyNewsEvents();
  
  document.getElementById("btn-refresh").addEventListener("click", handleRefresh);
  
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

