from typing import Dict, Any, List, Optional

def parse_num_from_str(s: str) -> float:
    """Helper to extract float from string like '0.3%', '211K', '-0.3'."""
    if not s or s == "-":
        return 0.0
    clean = str(s).replace("%", "").replace("K", "").replace("M", "").replace("B", "").replace(",", "").strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0

def has_valid_num(s: str) -> bool:
    if not s or str(s).strip() in ["-", "", "None"]:
        return False
    clean = str(s).replace("%", "").replace("K", "").replace("M", "").replace("B", "").replace(",", "").strip()
    try:
        float(clean)
        return True
    except ValueError:
        return False

def evaluate_past_actuals_regime(past_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Evaluates the macroeconomic regime from actual released data of preceding High Impact events
    (NFP, CPI, PPI, PMI, FOMC). Negative score = Hawkish USD / Bearish XAU (SELL);
    Positive score = Dovish USD / Bullish XAU (BUY).
    """
    if not past_events:
        return {
            "regime_score": 0.0,
            "regime_label": "NEUTRAL",
            "summary_text": ""
        }

    total_weighted = 0.0
    total_weights = 0.0
    event_summaries = []

    recent_events = past_events[-6:]
    total_ev = len(recent_events)

    for idx, ev in enumerate(recent_events):
        g_name = ev.get("group_name", "USD")
        recency_mult = 1.35 if idx >= total_ev - 2 else 1.0
        ev_details = []

        for it in ev.get("items", []):
            title_orig = it.get("title", "")
            title = title_orig.lower()
            a_str = str(it.get("actual", "")).strip()
            f_str = str(it.get("forecast", "-")).strip()
            p_str = str(it.get("previous", "-")).strip()

            if not has_valid_num(a_str):
                continue
            bench_str = f_str if has_valid_num(f_str) else (p_str if has_valid_num(p_str) else "")
            if not bench_str:
                continue

            a_val = parse_num_from_str(a_str)
            b_val = parse_num_from_str(bench_str)
            diff = a_val - b_val

            w = 2.0 * recency_mult
            dir_score = 0.0

            if "unemployment rate" in title:
                w = 2.4 * recency_mult
                if diff < -0.001:
                    dir_score = -1.25  # Lower unemployment = Hawkish USD = Bearish XAU
                elif diff > 0.001:
                    dir_score = 1.25
            elif "non-farm" in title or "nfp" in title or "payrolls" in title:
                w = 3.2 * recency_mult
                if diff > 0:
                    dir_score = -1.65 if diff >= 25 else -1.2
                elif diff < 0:
                    dir_score = 1.65 if diff <= -25 else 1.2
            elif "hourly earnings" in title:
                w = 2.6 * recency_mult
                if diff > 0.001:
                    dir_score = -1.4  # Hot wage inflation = Bearish XAU
                elif diff < -0.001:
                    dir_score = 1.3
            elif "cpi" in title or "inflation" in title:
                w = (3.4 if "core" in title or "m/m" in title else 2.5) * recency_mult
                if diff > 0.001:
                    dir_score = -1.75  # Hot CPI surprise = Strong Bearish XAU
                elif diff < -0.001:
                    dir_score = 1.75
                else:
                    dir_score = -0.6 if a_val >= 0.3 else 0.2
            elif "ppi" in title:
                w = 2.5 * recency_mult
                if diff > 0.001:
                    dir_score = -1.45
                elif diff < -0.001:
                    dir_score = 1.45
            elif "pmi" in title or "ism" in title:
                w = 2.0 * recency_mult
                if diff > 0.001:
                    dir_score = -1.1
                elif diff < -0.001:
                    dir_score = 1.1
            elif "funds rate" in title or "fomc" in title:
                w = 3.5 * recency_mult
                if diff > 0.001:
                    dir_score = -1.8
                elif diff < -0.001:
                    dir_score = 1.8

            if abs(dir_score) > 0.01:
                total_weighted += dir_score * w
                total_weights += w
                ev_details.append(f"{title_orig} Aktual {a_str} vs Forecast {bench_str}")

        if ev_details:
            event_summaries.append(f"{g_name} ({', '.join(ev_details[:2])})")

    if total_weights == 0:
        return {
            "regime_score": 0.0,
            "regime_label": "NEUTRAL",
            "summary_text": ""
        }

    norm = total_weighted / max(1.0, total_weights)
    regime_score = max(-4.8, min(4.8, round(norm * 3.0, 2)))
    if regime_score <= -1.0:
        regime_label = "SELL"
    elif regime_score >= 1.0:
        regime_label = "BUY"
    else:
        regime_label = "NEUTRAL"

    summary_text = "; ".join(event_summaries[-2:])
    return {
        "regime_score": regime_score,
        "regime_label": regime_label,
        "summary_text": summary_text
    }

def evaluate_event_consensus_bias(items: List[Dict[str, Any]], past_regime_score: float = 0.0) -> Dict[str, Any]:
    """
    Calculates directional macroeconomic bias from Forecast vs Previous in upcoming event items,
    incorporating Fed inflation target thresholds (0.2% m/m) and preceding actual releases regime
    to prevent false BUY signals when Previous had an extreme one-off spike.
    """
    macro_shift = 0.0
    weights_sum = 0.0
    signals_concordant = 0
    signals_count = 0

    for it in items:
        title = it.get("title", "").lower()
        f_str = str(it.get("forecast", "-")).strip()
        p_str = str(it.get("previous", "-")).strip()

        # Only compute numerical consensus shift when both Forecast and Previous are available
        if not has_valid_num(f_str) or not has_valid_num(p_str):
            continue

        f_val = parse_num_from_str(f_str)
        p_val = parse_num_from_str(p_str)

        diff = f_val - p_val
        weight = 1.0

        if "fomc" in title or "funds rate" in title or "interest rate" in title:
            weight = 3.5
            direction = -1.0 if diff >= 0 else 1.0
        elif "cpi" in title or "inflation" in title:
            is_mom = "m/m" in title or "mom" in title
            weight = 3.2 if ("core" in title and is_mom) else (2.8 if is_mom else 2.2)
            if diff > 0:
                direction = -1.0
            elif diff < 0:
                # Guard against mean-reversion illusion: >=0.3% m/m is still >=3.7% annualized sticky inflation
                if is_mom and f_val >= 0.3:
                    direction = -0.65 if past_regime_score <= -1.0 else -0.25
                elif is_mom and f_val >= 0.2 and past_regime_score <= -1.2:
                    # Preceding NFP/Wages came out hot, so 0.2% m/m forecast faces high upside surprise risk
                    direction = -0.45
                else:
                    direction = 1.0
            else:
                direction = -0.4 if (is_mom and f_val >= 0.3) else -0.3
        elif "ppi" in title:
            is_mom = "m/m" in title or "mom" in title
            weight = 2.8 if "core" in title else 2.5
            if diff > 0:
                direction = -1.0
            elif diff < 0:
                # Guard against high base-effect illusion (e.g. Forecast 0.3%-0.4% after 0.7%-1.3% spike)
                if is_mom and f_val >= 0.3:
                    direction = -0.75 if past_regime_score <= -1.0 else -0.30
                elif is_mom and f_val >= 0.2 and past_regime_score <= -1.2:
                    direction = -0.45
                else:
                    direction = 1.0
            else:
                direction = -0.3
        elif "pce" in title:
            weight = 2.8
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else -0.3)
        elif "non-farm" in title or "nfp" in title or "payrolls" in title:
            weight = 3.2
            # Higher payrolls = Bearish Gold; Lower payrolls = Bullish Gold
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else -0.3)
        elif "jobless" in title or "unemployment claims" in title or "initial claims" in title:
            weight = 2.0
            # Higher claims = Weaker jobs = Dovish USD = Bullish Gold
            direction = 1.0 if diff > 0 else (-1.0 if diff < 0 else -0.3)
        elif "unemployment rate" in title:
            weight = 2.2
            # Higher unemployment rate = Dovish USD = Bullish Gold
            direction = 1.0 if diff > 0 else (-1.0 if diff < 0 else -0.3)
        elif "pmi" in title or "ism" in title:
            weight = 2.6
            # Higher PMI = Stronger US activity = Hawkish USD = Bearish Gold; Lower PMI = Bullish Gold
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else (-0.3 if f_val >= 50.0 else 0.3))
        else:
            weight = 1.2
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else 0.0)

        contribution = direction * (1.5 if abs(diff) > 0.001 else 0.5)
        macro_shift += contribution * weight
        weights_sum += weight
        signals_count += 1
        if (contribution < 0 and macro_shift < 0) or (contribution > 0 and macro_shift > 0):
            signals_concordant += 1

    if signals_count == 0:
        return {
            "event_score": 0.0,
            "agreement": 0.5,
            "items_analyzed": 0
        }

    normalized_shift = macro_shift / max(1.0, weights_sum)
    event_score = normalized_shift * 4.5
    agreement = signals_concordant / max(1, signals_count)

    return {
        "event_score": round(event_score, 2),
        "agreement": agreement,
        "items_analyzed": signals_count
    }

def evaluate_actual_surprise_zscore(items: List[Dict[str, Any]], past_regime_score: float = 0.0) -> Dict[str, Any]:
    """
    Phase 2 (Flash Release): Evaluates real-time Actual vs Forecast surprises when actual prints land.
    Returns normalized surprise score, direction, fakeout risk, and human-readable summary.
    """
    surprise_shift = 0.0
    weights_sum = 0.0
    actual_parts = []
    valid_actuals = 0

    for it in items:
        title = it.get("title", "")
        t_low = title.lower()
        a_str = str(it.get("actual", "")).strip()
        f_str = str(it.get("forecast", "")).strip()

        if not a_str or a_str in ("-", "Pending") or not has_valid_num(a_str):
            continue

        a_val = parse_num_from_str(a_str)
        actual_parts.append(f"{title}: A {a_str} vs F {f_str or '-'}")
        valid_actuals += 1

        if not has_valid_num(f_str):
            continue

        f_val = parse_num_from_str(f_str)
        diff = a_val - f_val
        # Scale difference to unit surprise [-1.5 .. +1.5]
        if any(k in t_low for k in ("m/m", "mom", "y/y", "yoy", "rate", "cpi", "ppi", "pce")):
            step_scale = 0.1 if abs(f_val) < 2.0 else 0.25
        elif "pmi" in t_low or "ism" in t_low:
            step_scale = 0.8
        else:
            step_scale = max(abs(f_val) * 0.12, 20.0)

        mag = min(1.6, abs(diff) / max(step_scale, 0.05))
        if abs(diff) < 1e-6:
            mag = 0.0

        weight = 1.5
        # Inverse polarity metrics (Higher = Dovish USD = Bullish XAU)
        if any(k in t_low for k in ("unemployment rate", "jobless", "initial claims")):
            polarity = 1.0
            weight = 2.2
        elif any(k in t_low for k in ("core cpi", "core ppi", "non-farm", "payrolls", "nfp", "fomc", "funds rate")):
            polarity = -1.0
            weight = 3.2
        else:
            polarity = -1.0
            weight = 2.5

        if abs(diff) < 1e-6:
            # Inline print on sticky inflation (>=0.3% m/m) stays mildly hawkish
            dir_val = -0.25 if (("cpi" in t_low or "ppi" in t_low) and ("m/m" in t_low or "mom" in t_low) and a_val >= 0.3) else 0.0
        else:
            dir_val = (1.0 if diff > 0 else -1.0) * polarity * max(0.55, mag)

        surprise_shift += dir_val * weight
        weights_sum += weight

    if valid_actuals == 0:
        return {
            "has_actual": False,
            "surprise_score": 0.0,
            "surprise_norm": 0.0,
            "actual_summary": "",
            "surprise_label": "PRE-NEWS"
        }

    if weights_sum == 0:
        surprise_score = 0.0
    else:
        surprise_score = round((surprise_shift / weights_sum) * 4.5, 2)

    surprise_norm = max(-1.0, min(1.0, round(surprise_score / 4.5, 3)))
    if surprise_norm >= 0.15:
        surprise_label = "DOVISH SURPRISE (BULLISH XAU)"
    elif surprise_norm <= -0.15:
        surprise_label = "HAWKISH SURPRISE (BEARISH XAU)"
    else:
        surprise_label = "INLINE / MIXED ACTUAL"

    return {
        "has_actual": True,
        "surprise_score": surprise_score,
        "surprise_norm": surprise_norm,
        "actual_summary": " | ".join(actual_parts[:4]),
        "surprise_label": surprise_label
    }

def calculate_spike_potential(group_name: str, items: List[Dict[str, Any]], market_factors: Optional[Dict[str, Any]] = None) -> int:
    """Calculates spike potential percentage (60% - 98%) using event tier plus live XAU ATR H1 regime."""
    name_lower = group_name.strip().lower()

    if name_lower in ["fomc", "fomc press conference"]:
        base = 94
    elif name_lower == "nfp":
        base = 93
    elif name_lower == "cpi":
        base = 90
    elif name_lower == "ppi":
        base = 83
    elif name_lower in ["pmi", "ism pmi"]:
        base = 82
    else:
        base = 74

    if len(items) > 1:
        base = min(98, base + 2)

    if market_factors:
        atr_h1 = float(market_factors.get("xau_atr_h1", 0.0) or 0.0)
        if atr_h1 >= 20.0:
            base = min(98, base + 5)
        elif atr_h1 >= 14.0:
            base = min(98, base + 3)
        elif 0.0 < atr_h1 < 8.0:
            base = max(65, base - 5)

    return int(base)

def calculate_trajectory(spike_potential: int, agreement_ratio: float, xau_score: float) -> Dict[str, int]:
    """Calculates One-Way vs Two-Way probability."""
    decisiveness = min(1.0, abs(xau_score) / 7.0)
    one_way = int(45 + (decisiveness * 20) + (agreement_ratio * 15))
    one_way = max(35, min(80, one_way))
    two_way = 100 - one_way
    return {
        "one_way": one_way,
        "two_way": two_way
    }

def _format_items_summary(items: List[Dict[str, Any]]) -> str:
    parts = []
    for it in items[:4]:
        t = it.get("title", "Data")
        f = it.get("forecast", "-")
        p = it.get("previous", "-")
        if f != "-" or p != "-":
            parts.append(f"{t} (Forecast: {f} vs Previous: {p})")
        else:
            parts.append(t)
    return ", ".join(parts) if parts else "data konsensus resmi"

def generate_fundamental_dossier(
    group_name: str,
    items: List[Dict[str, Any]],
    expected_bias: str,
    final_score: float,
    spike_potential: int,
    past_regime: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates institutional macroeconomic fundamental reasoning, transmission mechanisms,
    consensus deviation rules, and key watch factors strictly matched to the scheduled event.
    """
    name_clean = group_name.strip()
    name_lower = name_clean.lower()
    items_summary = _format_items_summary(items)
    regime_summary = (past_regime or {}).get("summary_text", "")
    regime_score = (past_regime or {}).get("regime_score", 0.0)

    # 1. OFFICIAL NON-FARM PAYROLLS (NFP) ONLY
    if name_lower == "nfp":
        nfp_f, nfp_p = "-", "-"
        wage_f, wage_p = "-", "-"
        unemp_f, unemp_p = "-", "-"
        for it in items:
            t = it.get("title", "").lower()
            if ("non-farm" in t or "payrolls" in t or "nfp" in t) and "adp" not in t:
                nfp_f = it.get("forecast", "-") or "-"
                nfp_p = it.get("previous", "-") or "-"
            elif "hourly" in t:
                wage_f = it.get("forecast", "-") or "-"
                wage_p = it.get("previous", "-") or "-"
            elif "unemployment rate" in t:
                unemp_f = it.get("forecast", "-") or "-"
                unemp_p = it.get("previous", "-") or "-"

        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** berdasarkan rincian rilis NFP ({items_summary}). "
                f"Proyeksi perlambatan penciptaan lapangan kerja Non-Farm dibanding periode sebelumnya mencerminkan pendinginan pasar tenaga kerja AS (cooling labor market). "
                f"Kondisi ini memperbesar ruang bagi The Federal Reserve untuk memangkas suku bunga acuan, menekan Indeks Dolar AS (DXY) dan imbal hasil US Treasury 10Y, "
                f"sehingga mendorong arus akumulasi institusional pada emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** berdasarkan rincian rilis NFP ({items_summary}). "
                f"Konsensus ketenagakerjaan menunjukkan pasar kerja AS masih ekspansif dan ketat. "
                f"Ketahanan payrolls dan upah membatasi urgensi pemangkasan suku bunga The Fed (Higher for Longer), "
                f"menopang kekuatan Dolar AS (DXY) serta memberikan tekanan koreksi pada emas (XAU/USD)."
            )
        else:
            why_bias = (
                f"Konsensus rilis NFP ({items_summary}) berada di zona berimbang terhadap periode sebelumnya, "
                f"menciptakan pertarungan likuiditas ketat antara pembeli dan penjual menjelang detik rilis data resmi."
            )

        market_transmission = (
            "1. Transmisi Mandat Ganda Fed: Ketenagakerjaan adalah pilar utama The Fed selain stabilitas inflasi. Pelemahan lapangan kerja memperkuat ekspektasi pemangkasan suku bunga acuan.\n"
            "2. Dinamika DXY & Yields: Saat data payrolls di bawah konsensus, yield US 10-Year turun dan DXY tertekan, mengurangi opportunity cost memegang emas spot sehingga memicu arus beli institusi.\n"
            "3. Risiko Whipsaw Multi-Komponen: Volatilitas awal dikemudikan oleh angka Non-Farm Employment Change, namun kelanjutan tren 15 menit berikutnya ditentukan oleh Unemployment Rate dan Average Hourly Earnings."
        )

        consensus_rules = [
            {
                "condition": "Data Mendingin / Dovish USD (Bullish XAU)",
                "trigger": f"Actual Payrolls < Forecast ({nfp_f}) & Unemployment Rate >= {unemp_f}",
                "dxy_yield_reaction": "DXY anjlok menembus support, Yield US 10Y turun tajam",
                "xau_reaction": "🔺 Reli Kencang Vertikal (XAU Flash Pump)",
                "expected_pips": "+80 hingga +160 pips",
                "action": "Follow BUY momentum / Buy on breakout"
            },
            {
                "condition": "Data Panas / Hawkish USD (Bearish XAU)",
                "trigger": f"Actual Payrolls > Forecast ({nfp_f}) & Unemployment Rate lebih rendah",
                "dxy_yield_reaction": "Dolar AS melonjak perkasa, Yield US 10Y rebound tajam",
                "xau_reaction": "🔻 Tekanan Jual Masif (XAU Flash Dump)",
                "expected_pips": "-70 hingga -140 pips",
                "action": "Follow SELL momentum / Short on pullbacks"
            },
            {
                "condition": "Data Mixed / Whipsaw Dua Arah",
                "trigger": "Payrolls melemah namun Average Hourly Earnings melonjak di atas konsensus",
                "dxy_yield_reaction": "DXY berfluktuasi bolak-balik tanpa arah tren tegas",
                "xau_reaction": "🔄 Sapu Likuiditas Dua Arah (Whipsaw Ekstrem)",
                "expected_pips": "Ayunan 40 - 70 pips naik & turun",
                "action": "Hindari entry detik pertama; tunggu konfirmasi candle M5"
            }
        ]

        key_watch_factors = [
            {"factor": "Non-Farm Employment Change", "benchmark": f"Forecast: {nfp_f} | Previous: {nfp_p}", "importance": "Indikator Utama Volatilitas Detik Rilis (Deviasi >25K-30K)"},
            {"factor": "Unemployment Rate", "benchmark": f"Forecast: {unemp_f} | Previous: {unemp_p}", "importance": "Barometer Keseimbangan Pasar Tenaga Kerja AS"},
            {"factor": "Average Hourly Earnings m/m", "benchmark": f"Forecast: {wage_f} | Previous: {wage_p}", "importance": "Komponen Inflasi Upah Penentu Arah Lanjutan"}
        ]

        return {
            "event_type": "NFP",
            "event_badge": "🔴 TIER-1 ULTRA HIGH IMPACT",
            "headline_summary": "Laporan Resmi Ketenagakerjaan AS (Non-Farm Payrolls, Tingkat Pengangguran, & Upah Rata-Rata).",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Pasang batas risiko realistis (SL 45-60 pips) karena pelebaran spread saat NFP. Pantau penutupan candle M5 pertama untuk memvalidasi tren One-Way."
        }

    # 2. CONSUMER PRICE INDEX (CPI)
    elif name_lower == "cpi" or "inflation" in name_lower:
        core_m_f, core_m_p = "-", "-"
        cpi_m_f, cpi_m_p = "-", "-"
        cpi_y_f, cpi_y_p = "-", "-"
        for it in items:
            t = it.get("title", "").lower()
            if "core" in t and "m/m" in t:
                core_m_f, core_m_p = it.get("forecast", "-"), it.get("previous", "-")
            elif "cpi m/m" in t:
                cpi_m_f, cpi_m_p = it.get("forecast", "-"), it.get("previous", "-")
            elif "cpi y/y" in t and "core" not in t:
                cpi_y_f, cpi_y_p = it.get("forecast", "-"), it.get("previous", "-")

        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** berdasarkan komparasi data konsensus CPI AS ({items_summary}). "
                f"Proyeksi melandainya laju inflasi bulanan (Core CPI m/m di {core_m_f} dari {core_m_p} serta CPI m/m di {cpi_m_f} dari {cpi_m_p}) "
                f"memperkuat keyakinan bahwa tekanan harga sedang mereda (disinflasi). Hal ini memperbesar ruang pelonggaran moneter The Fed, "
                f"menekan imbal hasil riil (real yields) obligasi AS dan DXY, yang menjadi katalis pendorong utama kenaikan emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** berdasarkan komparasi data konsensus CPI AS ({items_summary}). "
                f"Proyeksi inflasi yang masih persisten (sticky inflation) memaksa The Fed mempertahankan suku bunga tinggi lebih lama (Higher for Longer), "
                f"mengerek imbal hasil US Treasury dan memperkuat Dolar AS sehingga menekan valuasi emas spot (XAU/USD)."
            )
        else:
            why_bias = (
                f"Data konsensus CPI AS ({items_summary}) berada di titik keseimbangan terhadap periode sebelumnya; "
                f"pelaku pasar menanti deviasi aktual minimal 0.1% pada Core CPI m/m sebagai pemicu arah tren utama."
            )

        market_transmission = (
            "1. Transmisi Real Yields: Emas memiliki korelasi negatif yang sangat kuat dengan imbal hasil riil AS (Yield Nominal dikurangi Ekspektasi Inflasi). Penurunan inflasi yang diikuti turunnya yield obligasi adalah pendorong fundamental utama reli emas.\n"
            "2. Core CPI vs Headline CPI: Bank sentral dan institusi memprioritaskan Core CPI m/m (tanpa pangan & energi). Deviasi 0.1% saja pada Core CPI m/m dapat menggerakkan harga emas 60-120 pips secara instan.\n"
            "3. Repricing Suku Bunga Fed: Angka aktual CPI secara langsung menggeser probabilitas suku bunga pada CME FedWatch Tool."
        )

        consensus_rules = [
            {
                "condition": "Disinflasi / Dovish USD (Bullish XAU)",
                "trigger": f"Actual Core CPI m/m <= {core_m_f} dan CPI m/m < {cpi_m_p}",
                "dxy_yield_reaction": "DXY menembus support harian, Yield US 10Y turun tajam",
                "xau_reaction": "🔺 Reli Tren Terarah (XAU Flash Pump)",
                "expected_pips": "+70 hingga +150 pips",
                "action": "Buy on breakout / Follow bullish momentum"
            },
            {
                "condition": "Inflasi Panas / Hawkish USD (Bearish XAU)",
                "trigger": f"Actual Core CPI m/m > {core_m_f} (di atas konsensus)",
                "dxy_yield_reaction": "DXY melonjak tajam, Yield US Treasury meroket",
                "xau_reaction": "🔻 Aksi Jual Agresif (XAU Flash Dump)",
                "expected_pips": "-60 hingga -130 pips",
                "action": "Follow Sell momentum"
            },
            {
                "condition": "Mixed (Headline Turun, Core Naik)",
                "trigger": "Headline CPI melandai namun Core CPI m/m melampaui perkiraan",
                "dxy_yield_reaction": "Ayunan volatilitas tajam di DXY sebelum menguat kembali",
                "xau_reaction": "🔄 Fakeout spike awal diikuti pembalikan arah",
                "expected_pips": "Ayunan 50 - 80 pips",
                "action": "Tunggu penutupan candle M5 dengan mengacu pada arah Core CPI"
            }
        ]

        key_watch_factors = [
            {"factor": "Core CPI m/m", "benchmark": f"Forecast: {core_m_f} | Previous: {core_m_p}", "importance": "Metrik Paling Kritis Pilihan The Fed (Tanpa Pangan & Energi)"},
            {"factor": "Headline CPI m/m", "benchmark": f"Forecast: {cpi_m_f} | Previous: {cpi_m_p}", "importance": "Penggerak Utama Reaksi Algoritma Detik Pertama"},
            {"factor": "Headline CPI y/y", "benchmark": f"Forecast: {cpi_y_f} | Previous: {cpi_y_p}", "importance": "Barometer Tren Inflasi Tahunan terhadap Target 2.0% Fed"}
        ]

        return {
            "event_type": "CPI",
            "event_badge": "🔴 TIER-1 INFLATION RADAR",
            "headline_summary": f"Rilis Indeks Harga Konsumen AS (CPI) — {items_summary} — penentu utama arah imbal hasil riil dan kebijakan The Fed.",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Rilis CPI cenderung membentuk tren satu arah (One-Way Trend) yang kuat apabila Core CPI m/m menyimpang >=0.1% dari konsensus."
        }

    # 3. PRODUCER PRICE INDEX (PPI)
    elif name_lower == "ppi":
        core_ppi_f, core_ppi_p = "-", "-"
        ppi_f, ppi_p = "-", "-"
        for it in items:
            t = it.get("title", "").lower()
            if "core ppi" in t:
                core_ppi_f, core_ppi_p = it.get("forecast", "-"), it.get("previous", "-")
            elif "ppi" in t:
                ppi_f, ppi_p = it.get("forecast", "-"), it.get("previous", "-")

        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** berdasarkan konsensus rilis PPI AS ({items_summary}). "
                f"Penurunan proyeksi inflasi tingkat produsen (Core PPI m/m di {core_ppi_f} dari {core_ppi_p} dan PPI m/m di {ppi_f} dari {ppi_p}) "
                f"menunjukkan meredanya tekanan biaya di tingkat pabrik/hulu. Hal ini menurunkan proyeksi komponen Core PCE The Fed, "
                f"melemahkan Dolar AS (DXY), dan mendorong penguatan harga emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** berdasarkan konsensus rilis PPI AS ({items_summary})"
                + (f" serta korelasi langsung dari data aktual sebelumnya yang keluar panas ({regime_summary}). " if regime_summary else ". ")
                + f"Meskipun Forecast bulanan terlihat lebih rendah dari lonjakan ekstrem periode lalu ({core_ppi_p} / {ppi_p}), "
                f"laju inflasi produsen {core_ppi_f}–{ppi_f} m/m masih berada di atas ambang stabilitas The Fed (0.2% m/m) dan berisiko kembali meleset naik mengikuti panasnya CPI & NFP, "
                f"sehingga memperkuat siklus Hawkish USD dan tekanan jual pada emas (XAU/USD)."
            )
        else:
            why_bias = (
                f"Konsensus rilis PPI AS ({items_summary}) berada di level seimbang; pasar menantikan deviasi aktual pada PPI m/m dan Core PPI m/m."
            )

        market_transmission = (
            "1. Transmisi Inflasi Hulu ke PCE: Komponen PPI (khususnya jasa keuangan, penerbangan, dan medis) merupakan input langsung perhitungan Core PCE yang menjadi acuan utama The Fed.\n"
            "2. Reaksi Yield & DXY: PPI yang lebih rendah dari konsensus memicu penurunan yield US Treasury dan pelemahan DXY, membuka ruang reli bagi XAU/USD.\n"
            f"3. Potensi Volatilitas: Model mengkalkulasi potensi spike {spike_potential}% pada pembukaan sesi New York."
        )

        consensus_rules = [
            {
                "condition": "PPI Mendingin / Dovish USD (Bullish XAU)",
                "trigger": f"Actual Core PPI m/m <= {core_ppi_f} dan PPI m/m <= {ppi_f}",
                "dxy_yield_reaction": "DXY terkoreksi turun, Yield obligasi AS melandai",
                "xau_reaction": "🔺 Penguatan Terarah (XAU Rally)",
                "expected_pips": "+50 hingga +110 pips",
                "action": "Buy on breakout / Pullback support"
            },
            {
                "condition": "PPI Panas / Hawkish USD (Bearish XAU)",
                "trigger": f"Actual Core PPI m/m > {core_ppi_f} atau PPI m/m melonjak",
                "dxy_yield_reaction": "DXY menguat cepat, Yield US 10Y naik",
                "xau_reaction": "🔻 Tekanan Jual Intraday (XAU Drop)",
                "expected_pips": "-50 hingga -100 pips",
                "action": "Follow Sell momentum"
            },
            {
                "condition": "Data Sesuai Konsensus / Mixed",
                "trigger": "Angka PPI dan Core PPI saling bertolak belakang",
                "dxy_yield_reaction": "Fluktuasi terbatas dalam rentang intraday",
                "xau_reaction": "🔄 Konsolidasi dua arah menguji Support/Resistance",
                "expected_pips": "Rentang 30 - 50 pips",
                "action": "Tunggu konfirmasi arah candle M5"
            }
        ]

        key_watch_factors = [
            {"factor": "Core PPI m/m", "benchmark": f"Forecast: {core_ppi_f} | Previous: {core_ppi_p}", "importance": "Indikator Utama Biaya Produksi Inti & Input Core PCE"},
            {"factor": "Headline PPI m/m", "benchmark": f"Forecast: {ppi_f} | Previous: {ppi_p}", "importance": "Barometer Tekanan Harga Grosir & Komoditas"}
        ]

        return {
            "event_type": "PPI",
            "event_badge": "🔴 TIER-1 PRODUCER INFLATION",
            "headline_summary": f"Rilis Indeks Harga Produsen AS (PPI) — {items_summary} — indikator utama inflasi hulu dan input Core PCE.",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Perhatikan keselarasan antara Core PPI dan Headline PPI pada detik rilis sebelum mengambil posisi."
        }

    # 4. OFFICIAL FOMC INTEREST RATE DECISION ONLY
    elif name_lower in ["fomc", "fomc press conference"]:
        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant memproyeksikan bias **XAU BUY (Skor {final_score:+.2f})** pada jadwal resmi FOMC ({items_summary}) "
                f"seiring ekspektasi pelonggaran kebijakan moneter atau panduan suku bunga yang dovish. "
                f"Penurunan ekspektasi suku bunga The Fed memangkas yield obligasi dan menekan Dolar AS, menguntungkan emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** pada jadwal resmi FOMC ({items_summary}) "
                f"didorong oleh sikap The Fed yang mempertahankan suku bunga ketat atau proyeksi kebijakan yang hawkish, "
                f"yang menopang DXY dan memicu tekanan jual pada emas."
            )
        else:
            why_bias = (
                f"Keputusan suku bunga FOMC ({items_summary}) diproyeksikan sesuai konsensus pasar; fokus utama tertuju pada pernyataan resmi dan Konferensi Pers Ketua The Fed."
            )

        market_transmission = (
            "1. Transmisi Dua Fase FOMC: Fase 1 adalah rilis Federal Funds Rate, FOMC Statement, dan Dot Plot. Fase 2 (30 menit kemudian) adalah Konferensi Pers Ketua The Fed yang kerap memicu pembalikan arah.\n"
            "2. Biaya Oportunitas Emas: Penurunan proyeksi suku bunga acuan menurunkan imbal hasil deposito dolar dan mengangkat valuasi emas.\n"
            "3. Proyeksi Ekonomi (SEP): Panduan suku bunga jangka menengah anggota FOMC menjadi kompas utama arus modal institusional."
        )

        consensus_rules = [
            {
                "condition": "Dovish Stance / Rate Cut (Bullish XAU)",
                "trigger": "Pemangkasan suku bunga atau panduan Statement/Dot Plot yang dovish",
                "dxy_yield_reaction": "Dolar AS melemah tajam, Yield US Treasury turun",
                "xau_reaction": "🔺 Lonjakan Vertikal Bullish (XAU Mega Pump)",
                "expected_pips": "+100 hingga +220 pips",
                "action": "Follow BUY momentum"
            },
            {
                "condition": "Hawkish Stance / Rate Hold (Bearish XAU)",
                "trigger": "Suku bunga ditahan tinggi dengan nada pernyataan tegas (hawkish)",
                "dxy_yield_reaction": "Dolar AS menguat menembus resistance, Yields naik",
                "xau_reaction": "🔻 Penurunan Tajam (XAU Flash Drop)",
                "expected_pips": "-90 hingga -180 pips",
                "action": "Follow SELL momentum"
            },
            {
                "condition": "Press Conference Reversal",
                "trigger": "Statement terbaca dovish namun sesi tanya-jawab bernada hawkish (atau sebaliknya)",
                "dxy_yield_reaction": "Pembalikan arah tajam saat konferensi pers berlangsung",
                "xau_reaction": "🔄 Whipsaw 2 Arah (Bull/Bear Trap)",
                "expected_pips": "Ayunan 80 - 140 pips",
                "action": "Amankan profit tahap pertama sebelum sesi tanya-jawab dimulai"
            }
        ]

        key_watch_factors = [
            {"factor": "Federal Funds Rate", "benchmark": items_summary, "importance": "Keputusan Suku Bunga Acuan Resmi The Fed"},
            {"factor": "FOMC Statement & Projections", "benchmark": "Panduan Kebijakan Moneter", "importance": "Penentu Ekspektasi Suku Bunga Kuartal Mendatang"},
            {"factor": "FOMC Press Conference", "benchmark": "Sesi Tanya Jawab Ketua Fed", "importance": "Pemicu Volatilitas Gelombang Kedua"}
        ]

        return {
            "event_type": "FOMC",
            "event_badge": "🔥 MONETARY POLICY DECISION",
            "headline_summary": "Pengumuman Resmi Suku Bunga The Fed (FOMC), Pernyataan Kebijakan Moneter, dan Konferensi Pers.",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Gunakan Stop Loss disiplin pada saat pengumuman FOMC dan waspadai volatilitas gelombang kedua saat konferensi pers."
        }

    # 5. PURCHASING MANAGERS' INDEX (PMI - ISM / FLASH PMI)
    else:
        first_f = items[0].get("forecast", "-") if items else "-"
        first_p = items[0].get("previous", "-") if items else "-"
        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** berdasarkan konsensus rilis **PMI AS** ({items_summary}). "
                f"Proyeksi melambatnya indeks aktivitas manufaktur/jasa ({first_f} vs {first_p}) menandakan pendinginan ekspansi bisnis AS. "
                f"Pelemahan PMI menekan imbal hasil US Treasury 10Y serta Indeks Dolar AS (DXY), sehingga memicu akumulasi beli institusional pada emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** berdasarkan konsensus rilis **PMI AS** ({items_summary}). "
                f"Ketahanan aktivitas sektor manufaktur dan jasa di zona ekspansi ({first_f} vs {first_p}) memperkuat argumen bahwa ekonomi AS masih solid, "
                f"mendukung penguatan Dolar AS (DXY) dan membatasi kenaikan emas (XAU/USD)."
            )
        else:
            why_bias = (
                f"Konsensus rilis **PMI AS** ({items_summary}) berada di level seimbang terhadap periode sebelumnya; "
                f"pasar menantikan deviasi aktual terhadap ambang batas ekspansi 50.0."
            )

        market_transmission = (
            "1. Ambang Kritis 50.0 (Ekspansi vs Kontraksi): Angka PMI di atas 50.0 menandakan ekspansi aktivitas bisnis yang menopang USD, sedangkan angka di bawah 50.0 menandakan kontraksi ekonomi yang memicu spekulasi pemangkasan suku bunga The Fed.\n"
            "2. Transmisi ke DXY & Real Yields: Kejutan PMI di bawah konsensus menekan yield obligasi AS dan DXY secara langsung pada sesi New York, mengangkat harga XAU/USD.\n"
            f"3. Potensi Volatilitas: Model mengkalkulasi potensi spike {spike_potential}% saat rilis data PMI."
        )

        consensus_rules = [
            {
                "condition": "PMI Melemah / Kontraksi (Bullish XAU)",
                "trigger": f"Actual PMI < Forecast ({first_f}) atau turun menembus < 50.0",
                "dxy_yield_reaction": "DXY tertekan turun, Yield US 10Y melandai tajam",
                "xau_reaction": "🔺 Reli Kenaikan Terarah (XAU BUY)",
                "expected_pips": "+50 hingga +110 pips",
                "action": "Buy on breakout / Pullback support"
            },
            {
                "condition": "PMI Ekspansif / Kuat (Bearish XAU)",
                "trigger": f"Actual PMI > Forecast ({first_f}) dan bertahan kuat di atas 50.0",
                "dxy_yield_reaction": "DXY menguat cepat, Yield obligasi AS naik",
                "xau_reaction": "🔻 Tekanan Jual Intraday (XAU SELL)",
                "expected_pips": "-50 hingga -105 pips",
                "action": "Follow Sell momentum"
            },
            {
                "condition": "Data Mixed (Manufaktur vs Jasa Berlawanan)",
                "trigger": "PMI Manufaktur dan PMI Jasa bergerak berlawanan arah terhadap konsensus",
                "dxy_yield_reaction": "Fluktuasi dua arah pada DXY",
                "xau_reaction": "🔄 Whipsaw Intraday (Uji Support & Resistance)",
                "expected_pips": "Rentang 35 - 60 pips",
                "action": "Tunggu konfirmasi candle M5 dengan prioritas pada Services PMI"
            }
        ]

        key_watch_factors = [
            {"factor": "Purchasing Managers' Index (PMI)", "benchmark": items_summary, "importance": "Barometer Utama Aktivitas Manufaktur & Jasa AS (Batas 50.0)"},
            {"factor": "US 10Y Treasury Yield & DXY", "benchmark": "Reaksi Sesi New York", "importance": "Konfirmasi Validitas Arah Pergerakan XAU/USD"}
        ]

        return {
            "event_type": "PMI",
            "event_badge": "🔴 TIER-1 ECONOMIC ACTIVITY (PMI)",
            "headline_summary": f"Rilis Indeks Manajer Pembelian AS (PMI) — {items_summary} — indikator utama ekspansi vs kontraksi ekonomi AS.",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Perhatikan deviasi angka aktual terhadap konsensus dan ambang 50.0 pada 5 menit pertama rilis."
        }

H3_WINDOW_SECONDS = 3 * 86400  # 3 days (72 hours = 259,200 seconds)

def _clamp_q(val: float, low: float, high: float) -> float:
    return max(low, min(high, float(val)))


def compute_full_quant_signal(
    next_event: Dict[str, Any],
    ai_analysis: Dict[str, Any],
    past_events: Optional[List[Dict[str, Any]]] = None,
    market_factors: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Produces the complete multi-factor AI Quantitative signal matched to the upcoming or just-released event.
    Phase 1 (Pre-News): Balanced Consensus + Past Actuals Regime + Live Intermarket (US10Y/DXY/Oil/XAU ATR) + AI/Geo.
    Phase 2 (Flash Release): Evaluates Actual vs Forecast Z-score with counter-spike fakeout detection.
    Enforces the H-3 rule when no allowed High Impact event is within 72 hours.
    """
    mf = market_factors or {}
    spike_pips_label = mf.get("spike_pips_label", "±145 - 255 pips")
    xau_atr_h1_pips = int(mf.get("xau_atr_h1_pips", 160) or 160)

    is_waiting = (
        not next_event
        or bool(next_event.get("is_waiting"))
        or next_event.get("group_name") == "WAITING NEWS"
        or int(next_event.get("seconds_until", 0)) > H3_WINDOW_SECONDS
    )

    if is_waiting:
        next_sched_group = next_event.get("next_scheduled_group") if next_event else None
        next_sched_wib = next_event.get("next_scheduled_wib") if next_event else None
        next_info_str = (
            f"Jadwal High Impact berikutnya adalah {next_sched_group} pada {next_sched_wib}."
            if next_sched_group and next_sched_wib
            else "Belum ada jadwal NFP, PPI, CPI, FOMC, atau PMI dalam 3 hari ke depan."
        )
        why_wait = (
            f"Status saat ini adalah **WAITING NEWS** karena tidak ada jadwal rilis berita High Impact utama "
            f"(**NFP, PPI, CPI, FOMC, PMI**) dalam rentang **3 hari (72 jam)** ke depan. "
            f"{next_info_str} Sesuai aturan **H-3**, hasil analisa AI Quant, skor bias XAU/USD, dan skenario deviasi "
            f"akan dikeluarkan secara otomatis tepat pada **H-3 (3 hari sebelum jadwal rilis berita)**."
        )
        waiting_dossier = {
            "event_type": "WAITING_NEWS",
            "event_badge": "⏳ STANDBY MODE • WAITING NEWS (ATURAN H-3)",
            "headline_summary": f"Tidak ada rilis NFP, PPI, CPI, FOMC, atau PMI dalam 3 hari ke depan. {next_info_str}",
            "why_bias_reason": why_wait,
            "market_interpretation": (
                "1. Filter Ketat 5 Berita Utama: Sistem hanya memantau 5 katalis High Impact penggerak utama XAU/USD yaitu NFP, PPI, CPI, FOMC, dan PMI.\n"
                "2. Protokol Rilis Analisa H-3: Analisa bias kuantitatif dan proyeksi deviasi konsensus dikunci hingga memasuki jendela H-3 (<= 72 jam sebelum rilis) agar data konsensus akurat dan tidak prematur.\n"
                "3. Fokus Perdagangan Saat Ini: Selama fase WAITING NEWS, pergerakan XAU/USD lebih dipengaruhi oleh struktur teknikal intraday, imbal hasil US 10Y Treasury, dan arus berita geopolitik harian."
            ),
            "consensus_rules": [
                {
                    "condition": "Status Kalender: WAITING NEWS (> 3 Hari)",
                    "trigger": "Tidak ada rilis NFP / PPI / CPI / FOMC / PMI dalam 72 jam ke depan",
                    "dxy_yield_reaction": "DXY dan Yield US 10Y bergerak mengikuti sentimen sesi harian & teknikal",
                    "xau_reaction": "⏳ Menunggu Jendela Analisa H-3",
                    "expected_pips": "Normal Intraday",
                    "action": "Gunakan analisis teknikal & pantau Tab Berita Harian"
                }
            ],
            "key_watch_factors": [
                {
                    "factor": "Jadwal High Impact Berikutnya",
                    "benchmark": f"{next_sched_group} ({next_sched_wib})" if next_sched_group else "Menunggu Jadwal Baru",
                    "importance": "Analisa AI Quant Keluar Otomatis pada H-3 (3 Hari Sebelum Rilis)"
                },
                {
                    "factor": "Live Intermarket & Volatilitas XAU",
                    "benchmark": f"US10Y {mf.get('yield_10y', '-')}% | DXY {mf.get('dxy_price', '-')} | ATR H1 {xau_atr_h1_pips} pips",
                    "importance": mf.get("intermarket_label", "Baseline Teknis & Obligasi Intraday")
                }
            ],
            "tactical_guidance": "Saat status WAITING NEWS aktif, hindari asumsi bias berita terlalu dini. Tunggu hasil analisa resmi keluar pada H-3 sebelum rilis."
        }

        return {
            "expected_bias": "WAITING NEWS",
            "context_percent": 0,
            "xau_score": 0.00,
            "spike_potential": 0,
            "one_way": 0,
            "two_way": 0,
            "ai_reasoning": why_wait,
            "geo_sentiment": ai_analysis.get("geopolitical_sentiment", "neutral") if ai_analysis else "neutral",
            "analysis_mode": "WAITING H-3",
            "phase": "WAITING_H3",
            "entry_mode": "STANDBY H-3",
            "spike_pips_label": spike_pips_label,
            "xau_atr_h1_pips": xau_atr_h1_pips,
            "quant_factors": {
                "phase": "WAITING_H3",
                "intermarket_score": round(float(mf.get("intermarket_score", 0.0) or 0.0), 3),
                "yield_10y": mf.get("yield_10y", 0.0),
                "yield_10y_5d_pct": mf.get("yield_10y_5d_pct", 0.0),
                "dxy_price": mf.get("dxy_price", 0.0),
                "dxy_rsi": mf.get("dxy_rsi", 50.0),
                "xau_price": mf.get("xau_price", 0.0),
                "xau_rsi": mf.get("xau_rsi", 50.0),
                "xau_stretch_z": mf.get("xau_stretch_z", 0.0),
                "oil_price": mf.get("oil_price", 0.0),
                "oil_5d_pct": mf.get("oil_5d_pct", 0.0),
                "xau_atr_h1_pips": xau_atr_h1_pips,
                "spike_pips_label": spike_pips_label,
                "counter_spike_risk": mf.get("counter_spike_risk", 0.35),
                "source_status": mf.get("source_status", "offline")
            },
            "why_bias_reason": why_wait,
            "market_interpretation": waiting_dossier["market_interpretation"],
            "consensus_rules": waiting_dossier["consensus_rules"],
            "key_watch_factors": waiting_dossier["key_watch_factors"],
            "tactical_guidance": waiting_dossier["tactical_guidance"],
            "fundamental_dossier": waiting_dossier
        }

    group_name = next_event.get("group_name", "USD News")
    items = next_event.get("items", [])

    # 1. Preceding actual releases macro regime (NFP, CPI, PPI, PMI, FOMC)
    past_regime = evaluate_past_actuals_regime(past_events)
    regime_score = float(past_regime.get("regime_score", 0.0) or 0.0)
    regime_summary = past_regime.get("summary_text", "")
    f_regime = _clamp_q(regime_score / 4.0, -1.0, 1.0)

    # 2. Event consensus deviation (Phase 1) & Real-time Actual Surprise (Phase 2)
    consensus = evaluate_event_consensus_bias(items, past_regime_score=regime_score)
    event_score = float(consensus.get("event_score", 0.0) or 0.0)
    f_consensus = _clamp_q(event_score / 4.5, -1.0, 1.0)

    actual_eval = evaluate_actual_surprise_zscore(items, past_regime_score=regime_score)
    has_actual = bool(actual_eval.get("has_actual"))
    f_surprise = float(actual_eval.get("surprise_norm", 0.0) or 0.0)

    # 3. Live Intermarket Quantitative Score (US10Y/5Y Yields, DXY Trend/RSI, Oil, XAU Stretch/ATR)
    f_intermarket = _clamp_q(float(mf.get("intermarket_score", 0.0) or 0.0), -1.0, 1.0)
    counter_spike_risk = float(mf.get("counter_spike_risk", 0.45) or 0.45)
    xau_stretch_z = float(mf.get("xau_stretch_z", 0.0) or 0.0)

    # 4. AI Macro & Geopolitical Sentiment
    geo_score = float((ai_analysis or {}).get("geo_score", 0.0) or 0.0)
    macro_score = float((ai_analysis or {}).get("macro_score", 0.0) or 0.0)
    f_ai_geo = _clamp_q((macro_score / 4.0) * 0.60 + (geo_score / 3.0) * 0.40, -1.0, 1.0)

    # Weighted Multi-Factor Score [-1.0 .. +1.0] -> [-9.90 .. +9.90]
    if has_actual:
        phase = "FLASH_RELEASE"
        weighted_norm = (
            (f_surprise * 0.45) +
            (f_regime * 0.20) +
            (f_intermarket * 0.20) +
            (f_ai_geo * 0.10) +
            (f_consensus * 0.05)
        )
    else:
        phase = "PRE_NEWS"
        weighted_norm = (
            (f_consensus * 0.30) +
            (f_regime * 0.25) +
            (f_intermarket * 0.25) +
            (f_ai_geo * 0.20)
        )

    final_score = _clamp_q(round(weighted_norm * 9.9, 2), -9.90, 9.90)

    # Determine Bias
    if final_score <= -1.35:
        expected_bias = "XAU SELL"
    elif final_score >= 1.35:
        expected_bias = "XAU BUY"
    else:
        expected_bias = "XAU NEUTRAL"

    # Two-Phase Entry Mode & Counter-Spike Stop-Hunt Guard
    structural_bear = (f_regime + f_intermarket) / 2.0 <= -0.35
    structural_bull = (f_regime + f_intermarket) / 2.0 >= 0.35

    if has_actual:
        if f_surprise > 0.08 and structural_bear and final_score < 0:
            entry_mode = "SPIKE UP FAKEOUT -> FADE SELL AFTER M5"
        elif f_surprise < -0.08 and structural_bull and final_score > 0:
            entry_mode = "SPIKE DOWN FAKEOUT -> FADE BUY AFTER M5"
        elif abs(final_score) >= 2.0:
            entry_mode = "FLASH CONFIRMED • FOLLOW ACTUAL"
        else:
            entry_mode = "MIXED PRINT • WAIT M5 CLOSE"
    else:
        overstretched_same_side = (
            (xau_stretch_z <= -1.4 and final_score <= -1.35) or
            (xau_stretch_z >= 1.4 and final_score >= 1.35)
        )
        factor_conflict = (f_consensus * f_intermarket < -0.10) or (f_regime * f_ai_geo < -0.12)
        if counter_spike_risk >= 0.65 or overstretched_same_side or factor_conflict:
            entry_mode = "WAIT M5 SPIKE"
        elif abs(final_score) >= 3.2:
            entry_mode = "FOLLOW BIAS (SL >= 1.2x ATR)"
        else:
            entry_mode = "LOW CONVICTION • WAIT ACTUAL"

    # Context confidence % (55% - 95%), penalized slightly when counter-spike/conflict is high
    factor_signs = [1 if v > 0.1 else (-1 if v < -0.1 else 0) for v in (f_surprise if has_actual else f_consensus, f_regime, f_intermarket, f_ai_geo)]
    non_zero = [s for s in factor_signs if s != 0]
    alignment_ratio = (abs(sum(non_zero)) / len(non_zero)) if non_zero else 0.5
    confidence = int(60 + (abs(final_score) / 9.9 * 25) + (alignment_ratio * 10) - (5 if entry_mode == "WAIT M5 SPIKE" and not has_actual else 0))
    confidence = max(55, min(95, confidence))

    # Spike potential incorporating live ATR
    spike = calculate_spike_potential(group_name, items, market_factors=mf)

    # Trajectory (boost two_way probability when M5 counter-spike guard triggers)
    effective_agreement = (consensus["agreement"] * 0.5 + alignment_ratio * 0.5)
    trajectory = calculate_trajectory(spike, effective_agreement, final_score)
    if entry_mode in ("WAIT M5 SPIKE", "SPIKE UP FAKEOUT -> FADE SELL AFTER M5", "SPIKE DOWN FAKEOUT -> FADE BUY AFTER M5"):
        two_way = max(trajectory["two_way"], 52)
        trajectory = {"one_way": 100 - two_way, "two_way": two_way}

    # Generate in-depth fundamental reasoning and market interpretation dossier
    dossier = generate_fundamental_dossier(
        group_name, items, expected_bias, final_score, spike, past_regime=past_regime
    )

    quant_note_parts = []
    if has_actual and actual_eval.get("actual_summary"):
        quant_note_parts.append(f"[FLASH ACTUAL] {actual_eval['actual_summary']} ({actual_eval['surprise_label']}).")
    if regime_summary:
        quant_note_parts.append(f"Rezim Aktual Sebelumnya: {regime_summary} (Skor {regime_score:+.2f}).")
    if mf.get("source_status") == "live":
        quant_note_parts.append(
            f"Intermarket Quant: US10Y {mf.get('yield_10y')}% ({mf.get('yield_10y_5d_pct'):+.1f}% 5D), "
            f"DXY {mf.get('dxy_price')}, XAU ATR H1 {xau_atr_h1_pips} pips (Estimasi Spike {spike_pips_label}), "
            f"Stretch Z={xau_stretch_z:+.2f}, Mode={entry_mode}."
        )
    if quant_note_parts:
        dossier["why_bias_reason"] = dossier.get("why_bias_reason", "") + " " + " ".join(quant_note_parts)

    extra_watch = []
    if mf.get("source_status") in ("live", "stale_cache"):
        extra_watch.append({
            "factor": "Intermarket & Volatilitas Live (Yields • DXY • ATR)",
            "benchmark": f"US10Y {mf.get('yield_10y')}% ({mf.get('yield_10y_5d_pct'):+.1f}% 5D) | DXY {mf.get('dxy_price')} | ATR H1 {xau_atr_h1_pips} pips",
            "importance": f"{mf.get('intermarket_label', 'Intermarket Quant')} • Potensi Sapuan {spike_pips_label} ({entry_mode})"
        })
    if regime_summary:
        extra_watch.append({
            "factor": "Korelasi Data Aktual Sebelumnya (NFP & CPI/PPI)",
            "benchmark": regime_summary,
            "importance": f"Pemberat Rezim Makro Berjalan ({past_regime['regime_label']} XAU)"
        })
    if extra_watch:
        dossier["key_watch_factors"] = extra_watch + dossier.get("key_watch_factors", [])

    if entry_mode == "WAIT M5 SPIKE":
        dossier["tactical_guidance"] = (
            f"SPIKE GUARD AKTIF ({spike_pips_label}): Posisi XAU saat ini sudah terstretch (Z={xau_stretch_z:+.2f}) "
            f"atau menghadapi risiko stop-hunt dua arah tinggi. Hindari entry sebelum rilis; tunggu candle M5 pertama "
            f"menyapu likuiditas terlebih dahulu, baru eksekusi mengikuti konfirmasi arah aktual + yields."
        )
    elif has_actual and "FAKEOUT" in entry_mode:
        dossier["tactical_guidance"] = (
            f"FLASH FAKEOUT GUARD ({actual_eval.get('surprise_label')}): Angka aktual headline memicu spike awal melawan "
            f"tekanan makro utama (Yields {mf.get('yield_10y')}% / DXY {mf.get('dxy_price')}). Tunggu rejection candle M5 ({spike_pips_label}) sebelum entry."
        )

    quant_factors = {
        "phase": phase,
        "entry_mode": entry_mode,
        "has_actual": has_actual,
        "actual_summary": actual_eval.get("actual_summary", ""),
        "surprise_label": actual_eval.get("surprise_label", "PRE-NEWS"),
        "spike_pips_label": spike_pips_label,
        "xau_atr_h1_pips": xau_atr_h1_pips,
        "counter_spike_risk": counter_spike_risk,
        "intermarket_score": round(f_intermarket, 3),
        "yield_10y": mf.get("yield_10y", 0.0),
        "yield_10y_5d_pct": mf.get("yield_10y_5d_pct", 0.0),
        "dxy_price": mf.get("dxy_price", 0.0),
        "dxy_rsi": mf.get("dxy_rsi", 50.0),
        "xau_price": mf.get("xau_price", 0.0),
        "xau_rsi": mf.get("xau_rsi", 50.0),
        "xau_stretch_z": round(xau_stretch_z, 2),
        "oil_price": mf.get("oil_price", 0.0),
        "oil_5d_pct": mf.get("oil_5d_pct", 0.0),
        "source_status": mf.get("source_status", "offline"),
        "weights": {
            "consensus_or_actual": round(f_surprise if has_actual else f_consensus, 3),
            "past_regime": round(f_regime, 3),
            "intermarket": round(f_intermarket, 3),
            "ai_geo": round(f_ai_geo, 3),
        }
    }

    return {
        "expected_bias": expected_bias,
        "context_percent": confidence,
        "xau_score": final_score,
        "spike_potential": spike,
        "one_way": trajectory["one_way"],
        "two_way": trajectory["two_way"],
        "phase": phase,
        "entry_mode": entry_mode,
        "spike_pips_label": spike_pips_label,
        "xau_atr_h1_pips": xau_atr_h1_pips,
        "quant_factors": quant_factors,
        "ai_reasoning": (ai_analysis or {}).get("summary_reasoning", ""),
        "geo_sentiment": (ai_analysis or {}).get("geopolitical_sentiment", "neutral"),
        "analysis_mode": (ai_analysis or {}).get("mode", "quant"),
        "why_bias_reason": dossier.get("why_bias_reason", ""),
        "market_interpretation": dossier.get("market_interpretation", ""),
        "consensus_rules": dossier.get("consensus_rules", []),
        "key_watch_factors": dossier.get("key_watch_factors", []),
        "tactical_guidance": dossier.get("tactical_guidance", ""),
        "fundamental_dossier": dossier
    }
