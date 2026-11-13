from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news
from modules.market_quant_service import get_market_quant_factors
from modules.ai_analyzer import analyze_with_llm
from modules.quant_engine import compute_full_quant_signal


def test_quant_v2_phases():
    mf = get_market_quant_factors(force_refresh=False)
    print(f"Live Market Quant: XAU={mf.get('xau_price')} ATR_H1={mf.get('xau_atr_h1_pips')}p ({mf.get('spike_pips_label')}) US10Y={mf.get('yield_10y')}% DXY={mf.get('dxy_price')} Intermarket={mf.get('intermarket_score')}")
    assert mf.get("xau_atr_h1_pips", 0) > 0, "ATR H1 pips must be positive"

    # Simulated Pre-News CPI with prior hot NFP regime
    past_hot = [{
        "group_name": "NFP",
        "datetime": "2026-11-06T13:30:00+00:00",
        "items": [
            {"title": "Non-Farm Employment Change", "actual": "165K", "forecast": "65K", "previous": "60K"},
            {"title": "Average Hourly Earnings m/m", "actual": "0.4%", "forecast": "0.3%", "previous": "0.3%"}
        ]
    }]
    cpi_pre = {
        "group_name": "CPI",
        "is_waiting": False,
        "seconds_until": 3600,
        "items": [
            {"title": "Core CPI m/m", "forecast": "0.2%", "previous": "0.3%"},
            {"title": "CPI m/m", "forecast": "0.3%", "previous": "0.6%"}
        ]
    }
    ai_bear = {"geo_score": 0.2, "macro_score": -1.5, "geopolitical_sentiment": "neutral", "summary_reasoning": "Yields elevated.", "mode": "test"}
    pre_sig = compute_full_quant_signal(cpi_pre, ai_bear, past_events=past_hot, market_factors=mf)
    print("CPI Pre-News Quant:", pre_sig["expected_bias"], pre_sig["xau_score"], "|", pre_sig["entry_mode"], "|", pre_sig["spike_pips_label"])
    assert pre_sig["phase"] == "PRE_NEWS"
    assert pre_sig["expected_bias"] == "XAU SELL", f"Expected XAU SELL under hot regime + elevated yields, got {pre_sig['expected_bias']}"
    assert -9.90 < pre_sig["xau_score"] < 0, "Multi-factor score should be nuanced negative, not forced"

    # Simulated Phase 2 Flash Release (Nov 13 PPI: 0.3% < 0.4% inside hawkish regime)
    ppi_flash = {
        "group_name": "PPI",
        "is_waiting": False,
        "seconds_until": 0,
        "items": [
            {"title": "Core PPI m/m", "actual": "0.3%", "forecast": "0.3%", "previous": "0.7%"},
            {"title": "PPI m/m", "actual": "0.3%", "forecast": "0.4%", "previous": "1.3%"}
        ]
    }
    flash_sig = compute_full_quant_signal(ppi_flash, ai_bear, past_events=past_hot, market_factors=mf)
    print("PPI Flash Quant   :", flash_sig["expected_bias"], flash_sig["xau_score"], "|", flash_sig["entry_mode"])
    assert flash_sig["phase"] == "FLASH_RELEASE"
    assert "FAKEOUT" in flash_sig["entry_mode"] or "WAIT M5" in flash_sig["entry_mode"], f"Expected fakeout guard on mixed PPI, got {flash_sig['entry_mode']}"


def main():
    test_quant_v2_phases()
    cal = get_economic_calendar()
    next_ev = cal["next_event"]
    news = get_latest_geopolitical_news()
    mf = get_market_quant_factors()
    ai_res = analyze_with_llm(news, next_ev["group_name"] if next_ev else "USD News", market_factors=mf)
    signal = compute_full_quant_signal(next_ev, ai_res, past_events=cal.get("past_events", []), market_factors=mf)

    print("\n=== LIVE QUANT SIGNAL OUTPUT ===")
    print("EXPECTED BIAS  :", signal["expected_bias"])
    print("PHASE / MODE   :", signal.get("phase"), "|", signal.get("entry_mode"))
    print("CONTEXT        :", f"{signal['context_percent']}%")
    print("XAU SCORE      :", signal["xau_score"])
    print("NEXT USD NEWS  :", next_ev["group_name"], f"({next_ev.get('countdown_str', '')})")
    print("SPIKE POTENTIAL:", f"{signal['spike_potential']}% ({signal.get('spike_pips_label')})")
    print("ONE-WAY / TWO  :", f"{signal['one_way']}% / {signal['two_way']}%")
    print("AI MODE        :", signal.get("analysis_mode"))
    print("AI REASONING   :", signal["ai_reasoning"])


if __name__ == "__main__":
    main()
