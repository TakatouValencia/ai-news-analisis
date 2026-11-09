import json
import asyncio
from modules.geopolitical_service import get_daily_macro_bulletins
from modules.calendar_service import get_economic_calendar, classify_event_group, is_high_impact_event, ALLOWED_GROUPS
from modules.quant_engine import compute_full_quant_signal
from modules.scheduler_service import scheduler
from main import get_state, get_daily_news_api, refresh_daily_news_api

def test_calendar_accuracy():
    print("1. Testing Strict 5-Event Whitelist (NFP, PPI, CPI, FOMC, PMI) & H-3 Rule...")
    # Ensure non-whitelisted events are strictly rejected
    rejected_titles = [
        "FOMC Member Waller Speaks",
        "Fed Chairman Warsh Speaks",
        "ADP Non-Farm Employment Change",
        "Unemployment Claims",
        "Initial Jobless Claims",
        "FOMC Meeting Minutes",
        "Retail Sales m/m",
        "Core PCE Price Index m/m",
        "Advance GDP q/q",
        "Philly Fed Manufacturing Index"
    ]
    for rt in rejected_titles:
        ev = {"title": rt, "country": "USD", "date": "2026-11-12T13:30:00+00:00", "impact": "High"}
        assert not is_high_impact_event(ev), f"{rt} must NOT be allowed!"
        assert classify_event_group(rt) == "", f"{rt} must classify as empty string!"

    # Ensure the 5 allowed groups classify accurately
    assert classify_event_group("Non-Farm Employment Change") == "NFP"
    assert classify_event_group("Core CPI m/m") == "CPI"
    assert classify_event_group("PPI m/m") == "PPI"
    assert classify_event_group("Federal Funds Rate") == "FOMC"
    assert classify_event_group("ISM Manufacturing PMI") == "PMI"
    assert classify_event_group("Flash Services PMI") == "PMI"

    cal = get_economic_calendar(force_refresh=True)
    for ev in cal.get("upcoming_events", []):
        assert ev["group_name"] in ALLOWED_GROUPS, f"Unexpected group in calendar: {ev['group_name']}"

    next_ev = cal.get("next_event")
    assert next_ev is not None, "Next event should not be None!"
    print(f"   -> Next Active Reading: {next_ev['group_name']} ({next_ev['datetime_wib']})")
    print(f"   -> Total Upcoming Allowed Events (NFP/PPI/CPI/FOMC/PMI): {len(cal.get('upcoming_events', []))}")

    # Test H-3 Waiting News Rule (> 3 days away -> WAITING NEWS)
    far_event = {
        "group_name": "NFP",
        "is_waiting": False,
        "seconds_until": 5 * 86400,  # 5 days away (> H-3)
        "next_scheduled_group": "NFP",
        "next_scheduled_wib": "Jumat, 04 Des 2026 | 20:30 WIB",
        "items": [{"title": "Non-Farm Employment Change", "forecast": "180K", "previous": "150K"}]
    }
    wait_sig = compute_full_quant_signal(far_event, {})
    assert wait_sig["expected_bias"] == "WAITING NEWS", "Events > 3 days away must return WAITING NEWS!"
    assert wait_sig["fundamental_dossier"]["event_type"] == "WAITING_NEWS"
    print("   -> H-3 Waiting News Rule verified (events > 3 days away return WAITING NEWS)!")

def test_daily_news():
    print("\n2. Testing get_daily_macro_bulletins()...")
    bulletins = get_daily_macro_bulletins(force_refresh=False)
    assert len(bulletins) > 0, "No bulletins found!"
    print(f"   -> Found {len(bulletins)} daily bulletins (strictly <= 48h old).")

    top = bulletins[0]
    print(f"   -> Top Bulletin: '{top['title'][:60]}...'")
    print(f"      Category: {top.get('category')} | Time: {top.get('published_time')}")
    interp = top.get("interpretation", {})
    assert "bias" in interp, "Missing bias in interpretation!"
    assert "transmission_mechanism" in interp, "Missing transmission mechanism!"
    assert "intermarket_matrix" in interp, "Missing intermarket matrix!"
    assert "tactical_action" in interp, "Missing tactical action!"
    print("   -> Interpretation structure is complete and valid!")

    print("\n3. Testing FastAPI endpoints (/api/state, /api/daily-news, /api/daily-news/refresh)...")
    async def _run_api_checks():
        res_state = await get_state(force=False)
        state_data = json.loads(res_state.body.decode("utf-8"))
        assert state_data.get("next_event") is not None, "State next_event missing!"
        assert state_data["signal"]["fundamental_dossier"]["event_type"] != "", "Dossier event_type missing!"

        res = await get_daily_news_api(force=False)
        data = json.loads(res.body.decode("utf-8"))
        assert data["status"] == "success", "Failed API status"
        print(f"   -> GET /api/daily-news returned {len(data['bulletins'])} items.")

        res_refresh = await refresh_daily_news_api()
        data_refresh = json.loads(res_refresh.body.decode("utf-8"))
        assert data_refresh["status"] == "success", "Failed refresh status"
        print("   -> POST /api/daily-news/refresh successfully refreshed bulletins!")

    asyncio.run(_run_api_checks())

    print("\n4. Testing Breaking News Web State update...")
    scheduler.check_and_update_web_breaking_news()
    assert scheduler.latest_breaking_bulletin is not None, "latest_breaking_bulletin should not be None"
    print(f"   -> scheduler.latest_breaking_bulletin is active: '{scheduler.latest_breaking_bulletin['title'][:50]}...'")

    print("\n[SUCCESS] All Calendar, Dossier, Daily News & Breaking News Automation Tests PASSED!")

if __name__ == "__main__":
    test_calendar_accuracy()
    test_daily_news()
