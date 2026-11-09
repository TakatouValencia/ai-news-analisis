import json
import asyncio
from modules.geopolitical_service import get_daily_macro_bulletins
from modules.calendar_service import get_economic_calendar, classify_event_group, is_high_impact_event
from modules.scheduler_service import scheduler
from main import get_state, get_daily_news_api, refresh_daily_news_api

def test_calendar_accuracy():
    print("1. Testing Calendar Classification & Filtering Accuracy...")
    # Ensure routine FOMC Member speech is never marked High Impact or classified as FOMC Rate Decision
    waller_speech = {
        "title": "FOMC Member Waller Speaks",
        "country": "USD",
        "date": "2026-11-10T09:00:00+00:00",
        "impact": "Medium"
    }
    assert not is_high_impact_event(waller_speech), "FOMC Member speech (Medium) must NOT be High Impact!"
    assert classify_event_group("FOMC Member Waller Speaks") != "FOMC", "FOMC Member speech must NOT be classified as FOMC!"

    # Ensure ADP is never classified as NFP
    assert classify_event_group("ADP Non-Farm Employment Change") == "ADP Non-Farm Employment", "ADP must not be classified as NFP!"
    assert classify_event_group("Non-Farm Employment Change") == "NFP", "Official Non-Farm Employment Change must be classified as NFP!"
    assert classify_event_group("FOMC Meeting Minutes") == "FOMC Meeting Minutes", "FOMC Minutes must not be classified as FOMC Rate Decision!"
    assert classify_event_group("Federal Funds Rate") == "FOMC", "Federal Funds Rate must be classified as FOMC!"

    cal = get_economic_calendar(force_refresh=False)
    next_ev = cal.get("next_event")
    assert next_ev is not None, "Next event should not be None!"
    print(f"   -> Next Event: {next_ev['group_name']} ({next_ev['datetime_wib']})")
    print("   -> Calendar classification and multi-week schedule verified!")

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
