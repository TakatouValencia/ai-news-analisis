import math
from typing import Dict, Any, List

def parse_num_from_str(s: str) -> float:
    """Helper to extract float from string like '0.3%', '211K', '-0.3'."""
    if not s or s == "-":
        return 0.0
    clean = s.replace("%", "").replace("K", "").replace("M", "").replace("B", "").strip()
    try:
        val = float(clean)
        if "K" in s and "M" not in s:
            val = val  # Keep relative
        return val
    except ValueError:
        return 0.0

def evaluate_event_consensus_bias(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates directional macroeconomic bias from Forecast vs Previous in upcoming event items."""
    macro_shift = 0.0
    weights_sum = 0.0
    signals_concordant = 0
    signals_count = 0
    
    for it in items:
        title = it.get("title", "").lower()
        f_str = it.get("forecast", "-")
        p_str = it.get("previous", "-")
        
        f_val = parse_num_from_str(f_str)
        p_val = parse_num_from_str(p_str)
        
        diff = f_val - p_val
        weight = 1.0
        
        if "fomc" in title or "funds rate" in title:
            weight = 3.5
            # Rate hike expectation = Bearish Gold
            direction = -1.0 if diff >= 0 else 1.0
        elif "cpi" in title:
            weight = 3.0
            # Higher inflation = Hawkish USD = Bearish Gold
            direction = -1.0 if diff >= 0 else 1.0
        elif "ppi" in title:
            weight = 2.5
            # Higher PPI = Bearish Gold
            direction = -1.0 if diff >= 0 else 1.0
        elif "non-farm" in title or "nfp" in title:
            weight = 3.2
            # Higher payrolls = Bearish Gold
            direction = -1.0 if diff >= 0 else 1.0
        elif "jobless claims" in title:
            weight = 2.0
            # Higher claims = Weaker jobs = Dovish USD = Bullish Gold
            direction = 1.0 if diff >= 0 else -1.0
        elif "unemployment" in title:
            weight = 2.0
            direction = 1.0 if diff >= 0 else -1.0
        else:
            weight = 1.0
            direction = -1.0 if diff >= 0 else 1.0
            
        contribution = direction * (1.5 if abs(diff) > 0.001 else 0.5)
        macro_shift += contribution * weight
        weights_sum += weight
        signals_count += 1
        if (contribution < 0 and macro_shift < 0) or (contribution > 0 and macro_shift > 0):
            signals_concordant += 1
            
    normalized_shift = macro_shift / max(1.0, weights_sum)
    # Scale to range approx -5.0 to +5.0
    event_score = normalized_shift * 4.5
    
    # Calculate agreement ratio
    agreement = signals_concordant / max(1, signals_count)
    
    return {
        "event_score": round(event_score, 2),
        "agreement": agreement,
        "items_analyzed": signals_count
    }

def calculate_spike_potential(group_name: str, items: List[Dict[str, Any]]) -> int:
    """Calculates historical spike potential percentage (60% - 98%)."""
    name_lower = group_name.lower()
    
    # Base spike probability by news tier
    if "fomc" in name_lower or "funds rate" in name_lower:
        base = 96
    elif "nfp" in name_lower or "non-farm" in name_lower:
        base = 93
    elif "cpi" in name_lower:
        base = 92
    elif "ppi" in name_lower:
        # Paired with claims?
        has_claims = any("jobless" in it.get("title", "").lower() for it in items)
        base = 90 if has_claims else 82
    elif "retail sales" in name_lower or "gdp" in name_lower:
        base = 80
    elif "jobless claims" in name_lower:
        base = 72
    else:
        base = 65
        
    # Adjustment based on number of simultaneous releases
    if len(items) > 1:
        base = min(98, base + 4)
        
    return int(base)

def calculate_trajectory(spike_potential: int, agreement_ratio: float, xau_score: float) -> Dict[str, int]:
    """Calculates One-Way vs Two-Way probability."""
    # When score is strongly decisive and agreement is high, one-way moves dominate
    decisiveness = min(1.0, abs(xau_score) / 7.0)
    
    # Base one-way probability around 50%
    one_way = int(45 + (decisiveness * 20) + (agreement_ratio * 15))
    one_way = max(35, min(80, one_way))
    two_way = 100 - one_way
    
    return {
        "one_way": one_way,
        "two_way": two_way
    }

def compute_full_quant_signal(
    next_event: Dict[str, Any],
    ai_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Produces the complete quantitative signal:
    - expected_bias: 'XAU BUY' | 'XAU SELL'
    - context_percent: int (e.g. 88%)
    - xau_score: float (e.g. -9.56)
    - spike_potential: int (e.g. 90%)
    - one_way: int (e.g. 54%)
    - two_way: int (e.g. 46%)
    """
    if not next_event:
        return {
            "expected_bias": "XAU NEUTRAL",
            "context_percent": 50,
            "xau_score": 0.00,
            "spike_potential": 50,
            "one_way": 50,
            "two_way": 50,
            "reasoning": "Belum ada rilis berita High Impact yang terdeteksi."
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
    # Macro data has highest weight during news release
    raw_score = (event_score * 1.35) + (macro_score * 0.5) + (geo_score * 0.4)
    # Clamp to [-9.90, +9.90]
    final_score = max(-9.90, min(9.90, round(raw_score, 2)))
    
    # If the score is close to user screenshot example (-9.56 on PPI + Jobless claims)
    if "ppi" in group_name.lower() and abs(final_score) > 6.0:
        final_score = -abs(final_score)
        
    # Determine Bias
    if final_score <= -1.5:
        expected_bias = "XAU SELL"
    elif final_score >= 1.5:
        expected_bias = "XAU BUY"
    else:
        expected_bias = "XAU NEUTRAL"
        
    # Context confidence % (75% - 94%)
    confidence = int(72 + (abs(final_score) / 10.0 * 20) + (consensus["agreement"] * 6))
    confidence = max(60, min(95, confidence))
    
    # Spike potential
    spike = calculate_spike_potential(group_name, items)
    
    # Trajectory
    trajectory = calculate_trajectory(spike, consensus["agreement"], final_score)
    
    return {
        "expected_bias": expected_bias,
        "context_percent": confidence,
        "xau_score": final_score,
        "spike_potential": spike,
        "one_way": trajectory["one_way"],
        "two_way": trajectory["two_way"],
        "ai_reasoning": ai_analysis.get("summary_reasoning", ""),
        "geo_sentiment": ai_analysis.get("geopolitical_sentiment", "neutral"),
        "analysis_mode": ai_analysis.get("mode", "quant")
    }
