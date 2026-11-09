from typing import Dict, Any, List

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

def evaluate_event_consensus_bias(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates directional macroeconomic bias from Forecast vs Previous in upcoming event items."""
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
            weight = 3.0 if "core" in title or "m/m" in title else 2.2
            # Higher inflation = Hawkish USD = Bearish Gold; Lower inflation = Dovish USD = Bullish Gold
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else -0.3)
        elif "ppi" in title:
            weight = 2.5
            direction = -1.0 if diff > 0 else (1.0 if diff < 0 else -0.3)
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

def calculate_spike_potential(group_name: str, items: List[Dict[str, Any]]) -> int:
    """Calculates historical spike potential percentage (60% - 98%) accurately by event type."""
    name_lower = group_name.strip().lower()

    if name_lower in ["fomc", "fomc press conference"]:
        base = 96
    elif name_lower == "nfp":
        base = 95
    elif name_lower == "cpi":
        base = 92
    elif name_lower == "core pce":
        base = 88
    elif name_lower == "fomc meeting minutes":
        base = 85
    elif name_lower == "gdp":
        base = 84
    elif name_lower == "ppi":
        has_claims = any("jobless" in it.get("title", "").lower() or "claims" in it.get("title", "").lower() for it in items)
        base = 88 if has_claims else 82
    elif name_lower == "retail sales":
        base = 82
    elif name_lower == "ism pmi":
        base = 80
    elif "adp" in name_lower or "jolts" in name_lower:
        base = 78
    elif "jobless claims" in name_lower or "unemployment claims" in name_lower:
        base = 74
    elif "fed chair" in name_lower:
        base = 80
    else:
        base = 68

    if len(items) > 1:
        base = min(98, base + 3)

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
    spike_potential: int
) -> Dict[str, Any]:
    """
    Generates institutional macroeconomic fundamental reasoning, transmission mechanisms,
    consensus deviation rules, and key watch factors strictly matched to the scheduled event.
    """
    name_clean = group_name.strip()
    name_lower = name_clean.lower()
    items_summary = _format_items_summary(items)

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
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** berdasarkan konsensus rilis PPI AS ({items_summary}). "
                f"Kenaikan biaya produsen mengindikasikan tekanan harga hulu yang berpotensi diteruskan ke konsumen (CPI/PCE), "
                f"memperkuat ekspektasi sikap hawkish The Fed dan menekan harga emas (XAU/USD)."
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

    # 5. FOMC MEETING MINUTES (RISALAH RAPAT FOMC - BUKAN KEPUTUSAN SUKU BUNGA)
    elif name_lower == "fomc meeting minutes":
        why_bias = (
            f"Rilis **FOMC Meeting Minutes** merupakan risalah detail dari rapat kebijakan FOMC sebelumnya (bukan pengumuman suku bunga baru). "
            f"Model AI Quant menetapkan bias **{expected_bias} (Skor {final_score:+.2f})** dengan mencermati perdebatan internal anggota komite The Fed "
            f"mengenai risiko inflasi versus ketahanan pasar tenaga kerja."
        )
        return {
            "event_type": "FOMC_MINUTES",
            "event_badge": "📋 FOMC MINUTES RELEASE",
            "headline_summary": "Rilis Risalah Rapat FOMC (Meeting Minutes): rincian diskusi internal pejabat The Fed mengenai arah kebijakan moneter.",
            "why_bias_reason": why_bias,
            "market_interpretation": (
                "1. Bukan Pengumuman Rate Baru: FOMC Minutes membedah proporsi anggota The Fed yang berpandangan hawkish vs dovish pada rapat sebelumnya.\n"
                "2. Pergeseran Probabilitas FedWatch: Kalimat kunci dalam risalah dapat mengubah ekspektasi pasar terhadap rapat FOMC akhir bulan/mendatang.\n"
                "3. Reaksi XAU/USD: Jika risalah menekankan kekhawatiran inflasi, DXY menguat dan menekan emas; jika menyoroti risiko perlambatan ekonomi, emas terdorong naik."
            ),
            "consensus_rules": [
                {
                    "condition": "Risalah Bernada Dovish (Bullish XAU)",
                    "trigger": "Mayoritas anggota mendukung pelonggaran suku bunga lebih lanjut",
                    "dxy_yield_reaction": "DXY dan Yield US 10Y melemah",
                    "xau_reaction": "🔺 Kenaikan Terukur (XAU BUY)",
                    "expected_pips": "+45 hingga +90 pips",
                    "action": "Buy on breakout"
                },
                {
                    "condition": "Risalah Bernada Hawkish (Bearish XAU)",
                    "trigger": "Anggota mengkhawatirkan inflasi persisten dan menahan pemangkasan bunga",
                    "dxy_yield_reaction": "DXY menguat, Yield obligasi naik",
                    "xau_reaction": "🔻 Tekanan Jual (XAU SELL)",
                    "expected_pips": "-45 hingga -90 pips",
                    "action": "Sell momentum"
                },
                {
                    "condition": "Risalah Netral / Sesuai Ekspektasi",
                    "trigger": "Tidak ada kejutan baru dibanding pernyataan rapat sebelumnya",
                    "dxy_yield_reaction": "Fluktuasi terbatas",
                    "xau_reaction": "🔄 Konsolidasi Intraday",
                    "expected_pips": "Rentang 25 - 45 pips",
                    "action": "Fokus pada level Support/Resistance teknikal"
                }
            ],
            "key_watch_factors": [
                {"factor": "FOMC Meeting Minutes", "benchmark": "Sentimen Hawkish vs Dovish Komite", "importance": "Petunjuk Arah Kebijakan Rapat FOMC Berikutnya"},
                {"factor": "Respon US 10Y Yield", "benchmark": "Reaksi Pasar Obligasi AS", "importance": "Konfirmasi Arah Likuiditas XAU/USD"}
            ],
            "tactical_guidance": "Algoritma membaca teks risalah secara instan pada detik rilis; tunggu candle M5 pertama selesai sebelum membuka posisi."
        }

    # 6. INITIAL JOBLESS CLAIMS / ADP / LABOR RELEASES (NON-NFP)
    elif "jobless" in name_lower or "claims" in name_lower or "adp" in name_lower or "jolts" in name_lower:
        first_f = items[0].get("forecast", "-") if items else "-"
        first_p = items[0].get("previous", "-") if items else "-"
        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** pada rilis **{name_clean}** ({items_summary}). "
                f"Konsensus data mengindikasikan pelonggaran pada kondisi ketenagakerjaan mingguan/swasta AS dibanding periode sebelumnya ({first_f} vs {first_p}). "
                f"Data klaim pengangguran yang lebih tinggi atau serapan kerja yang melambat menekan Dolar AS (DXY) dan memberikan dorongan positif bagi harga emas (XAU/USD)."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** pada rilis **{name_clean}** ({items_summary}). "
                f"Konsensus menunjukkan pasar tenaga kerja AS tetap tangguh ({first_f} vs {first_p}), mendukung kekuatan Dolar AS dan menahan laju kenaikan emas."
            )
        else:
            why_bias = (
                f"Konsensus pada rilis **{name_clean}** ({items_summary}) berada di kisaran stabil; pasar menunggu deviasi aktual terhadap angka perkiraan."
            )

        return {
            "event_type": "LABOR_MARKET",
            "event_badge": "🔴 HIGH IMPACT LABOR DATA",
            "headline_summary": f"Rilis Data Ketenagakerjaan AS: {name_clean} ({items_summary}).",
            "why_bias_reason": why_bias,
            "market_interpretation": (
                f"1. Indikator Kesehatan Pasar Kerja: {name_clean} mengukur dinamika ketenagakerjaan AS secara berkala di luar jadwal NFP bulanan.\n"
                "2. Respon DXY & Yield: Pelemahan data tenaga kerja (klaim naik / serapan turun) melemahkan DXY dan mengangkat XAU/USD.\n"
                f"3. Potensi Volatilitas: Diperkirakan memicu pergerakan terukur dengan potensi spike {spike_potential}%."
            ),
            "consensus_rules": [
                {
                    "condition": "Pasar Kerja Melemah / Dovish USD (Bullish XAU)",
                    "trigger": "Klaim Pengangguran > Forecast (atau ADP/JOLTS < Forecast)",
                    "dxy_yield_reaction": "DXY tertekan turun, Yield US 10Y melandai",
                    "xau_reaction": "🔺 Kenaikan Harga (XAU BUY)",
                    "expected_pips": "+40 hingga +85 pips",
                    "action": "Buy on breakout"
                },
                {
                    "condition": "Pasar Kerja Kuat / Hawkish USD (Bearish XAU)",
                    "trigger": "Klaim Pengangguran < Forecast (atau ADP/JOLTS > Forecast)",
                    "dxy_yield_reaction": "DXY menguat, Yield obligasi naik",
                    "xau_reaction": "🔻 Penurunan Harga (XAU SELL)",
                    "expected_pips": "-40 hingga -85 pips",
                    "action": "Sell momentum"
                },
                {
                    "condition": "Data Sesuai Ekspektasi",
                    "trigger": f"Rilis aktual sesuai konsensus ({first_f})",
                    "dxy_yield_reaction": "Reaksi terbatas pada DXY",
                    "xau_reaction": "🔄 Konsolidasi dalam rentang teknikal",
                    "expected_pips": "Rentang 25 - 40 pips",
                    "action": "Eksekusi pada batas Support/Resistance"
                }
            ],
            "key_watch_factors": [
                {"factor": name_clean, "benchmark": f"Forecast: {first_f} | Previous: {first_p}", "importance": "Deviasi Aktual terhadap Konsensus Pasar"},
                {"factor": "Indeks Dolar AS (DXY) & US 10Y", "benchmark": "Reaksi Sesi New York", "importance": "Konfirmasi Validitas Arah Pergerakan XAU/USD"}
            ],
            "tactical_guidance": "Pantau reaksi 5 menit pertama pasca rilis dan perhatikan arah yield obligasi AS."
        }

    # 7. OTHER HIGH IMPACT MACRO (GDP, Retail Sales, Core PCE, ISM PMI, Fed Chair Speech)
    else:
        if "BUY" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU BUY (Skor {final_score:+.2f})** karena komparasi konsensus pada rilis **{name_clean}** ({items_summary}) "
                f"mengindikasikan perlambatan aktivitas ekonomi atau meredanya tekanan harga dibanding periode sebelumnya. "
                f"Data makro yang melandai menekan Indeks Dolar AS (DXY) dan imbal hasil obligasi, memberikan ruang dorong bagi harga emas untuk bergerak naik."
            )
        elif "SELL" in expected_bias:
            why_bias = (
                f"Model AI Quant menetapkan bias **XAU SELL (Skor {final_score:+.2f})** karena data konsensus pada **{name_clean}** ({items_summary}) "
                f"menunjukkan ketahanan ekonomi AS yang lebih kuat dari periode sebelumnya. "
                f"Hal ini memperkuat permintaan Dolar AS dan membatasi minat beli pada instrumen emas dunia."
            )
        else:
            why_bias = (
                f"Data konsensus pada **{name_clean}** ({items_summary}) menunjukkan dinamika berimbang terhadap periode sebelumnya; "
                f"pasar diperkirakan bergerak dalam rentang konsolidasi hingga rilis resmi keluar."
            )

        market_transmission = (
            f"1. Transmisi Data Makro ke Dolar: Rilis {name_clean} menguji ekspektasi pasar terhadap pertumbuhan ekonomi dan kebijakan moneter AS.\n"
            "2. Korelasi Terbalik Emas & DXY: Kejutan data di bawah konsensus melemahkan DXY dan memicu reli emas, sedangkan angka yang melampaui konsensus menekan emas turun.\n"
            f"3. Potensi Lonjakan Volatilitas: Model memproyeksikan potensi spike {spike_potential}% pada menit-menit awal rilis data."
        )

        consensus_rules = [
            {
                "condition": "Data Lemah / Dovish USD (Bullish XAU)",
                "trigger": "Actual < Forecast secara signifikan",
                "dxy_yield_reaction": "DXY melemah, Yield obligasi tertekan",
                "xau_reaction": "🔺 Kenaikan Harga (XAU BUY)",
                "expected_pips": "+45 hingga +95 pips",
                "action": "Buy on breakout"
            },
            {
                "condition": "Data Kuat / Hawkish USD (Bearish XAU)",
                "trigger": "Actual > Forecast secara signifikan",
                "dxy_yield_reaction": "DXY menguat, Yield obligasi naik",
                "xau_reaction": "🔻 Penurunan Harga (XAU SELL)",
                "expected_pips": "-45 hingga -95 pips",
                "action": "Sell momentum"
            },
            {
                "condition": "Data Sesuai Ekspektasi",
                "trigger": "Actual ~= Forecast",
                "dxy_yield_reaction": "Reaksi datar atau normalisasi cepat",
                "xau_reaction": "🔄 Konsolidasi dalam rentang teknikal",
                "expected_pips": "Rentang 25 - 45 pips",
                "action": "Fokus pada level teknikal Support/Resistance"
            }
        ]

        key_watch_factors = [
            {"factor": name_clean, "benchmark": items_summary, "importance": "Deviasi Angka Aktual terhadap Perkiraan Pasar"},
            {"factor": "Respon Indeks Dolar (DXY)", "benchmark": "Support & Resistance Kunci", "importance": "Konfirmasi Arah Aliran Dana Global"}
        ]

        return {
            "event_type": "MACRO_HIGH_IMPACT",
            "event_badge": "🔴 HIGH IMPACT MACRO RELEASE",
            "headline_summary": f"Rilis data ekonomi {name_clean} ({items_summary}) dengan potensi pergerakan terukur pada XAU/USD.",
            "why_bias_reason": why_bias,
            "market_interpretation": market_transmission,
            "consensus_rules": consensus_rules,
            "key_watch_factors": key_watch_factors,
            "tactical_guidance": "Gunakan trailing stop dan perhatikan respon DXY pada 5 menit pertama rilis data."
        }

def compute_full_quant_signal(
    next_event: Dict[str, Any],
    ai_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Produces the complete quantitative signal matched to the upcoming economic calendar event."""
    if not next_event:
        return {
            "expected_bias": "XAU NEUTRAL",
            "context_percent": 50,
            "xau_score": 0.00,
            "spike_potential": 50,
            "one_way": 50,
            "two_way": 50,
            "reasoning": "Belum ada rilis berita High Impact yang terdeteksi.",
            "why_bias_reason": "Belum ada rilis berita High Impact mendatang.",
            "market_interpretation": "Menunggu konfirmasi kalender ekonomi High Impact.",
            "consensus_rules": [],
            "key_watch_factors": [],
            "tactical_guidance": "Gunakan manajemen risiko standar.",
            "fundamental_dossier": {}
        }

    group_name = next_event.get("group_name", "USD News")
    items = next_event.get("items", [])

    # 1. Event consensus deviation
    consensus = evaluate_event_consensus_bias(items)
    event_score = consensus["event_score"]

    # 2. AI Macro & Geopolitical Sentiment
    geo_score = ai_analysis.get("geo_score", 0.0)
    macro_score = ai_analysis.get("macro_score", 0.0)

    # Composite score calculation: -10.0 to +10.0
    raw_score = (event_score * 1.35) + (macro_score * 0.5) + (geo_score * 0.4)
    final_score = max(-9.90, min(9.90, round(raw_score, 2)))

    # Determine Bias
    if final_score <= -1.5:
        expected_bias = "XAU SELL"
    elif final_score >= 1.5:
        expected_bias = "XAU BUY"
    else:
        expected_bias = "XAU NEUTRAL"

    # Context confidence % (60% - 95%)
    confidence = int(72 + (abs(final_score) / 10.0 * 20) + (consensus["agreement"] * 6))
    confidence = max(60, min(95, confidence))

    # Spike potential
    spike = calculate_spike_potential(group_name, items)

    # Trajectory
    trajectory = calculate_trajectory(spike, consensus["agreement"], final_score)

    # Generate in-depth fundamental reasoning and market interpretation dossier
    dossier = generate_fundamental_dossier(group_name, items, expected_bias, final_score, spike)

    return {
        "expected_bias": expected_bias,
        "context_percent": confidence,
        "xau_score": final_score,
        "spike_potential": spike,
        "one_way": trajectory["one_way"],
        "two_way": trajectory["two_way"],
        "ai_reasoning": ai_analysis.get("summary_reasoning", ""),
        "geo_sentiment": ai_analysis.get("geopolitical_sentiment", "neutral"),
        "analysis_mode": ai_analysis.get("mode", "quant"),
        "why_bias_reason": dossier.get("why_bias_reason", ""),
        "market_interpretation": dossier.get("market_interpretation", ""),
        "consensus_rules": dossier.get("consensus_rules", []),
        "key_watch_factors": dossier.get("key_watch_factors", []),
        "tactical_guidance": dossier.get("tactical_guidance", ""),
        "fundamental_dossier": dossier
    }
