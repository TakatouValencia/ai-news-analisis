import sys
from pathlib import Path
from modules.calendar_service import get_economic_calendar
from modules.geopolitical_service import get_latest_geopolitical_news
from modules.ai_analyzer import analyze_with_llm
from modules.quant_engine import compute_full_quant_signal

def main():
    cal = get_economic_calendar()
    next_ev = cal["next_event"]
    news = get_latest_geopolitical_news()
    ai_res = analyze_with_llm(news, next_ev["group_name"] if next_ev else "USD News")
    signal = compute_full_quant_signal(next_ev, ai_res)

    print("=== QUANT SIGNAL OUTPUT ===")
    print("EXPECTED BIAS  :", signal["expected_bias"])
    print("CONTEXT        :", f"{signal['context_percent']}%")
    print("XAU SCORE      :", signal["xau_score"])
    print("NEXT USD NEWS  :", next_ev["group_name"], f"({next_ev.get('countdown_str', '')})")
    print("SPIKE POTENTIAL:", f"{signal['spike_potential']}%")
    print("ONE-WAY        :", f"{signal['one_way']}%")
    print("TWO-WAY        :", f"{signal['two_way']}%")
    print("AI REASONING   :", signal["ai_reasoning"])

if __name__ == "__main__":
    main()
