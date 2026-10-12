import json
from modules.geopolitical_service import get_daily_macro_bulletins
from modules.scheduler_service import scheduler
from fastapi.testclient import TestClient
from main import app

def test_daily_news():
    print("1. Testing get_daily_macro_bulletins()...")
    bulletins = get_daily_macro_bulletins(force_refresh=False)
    assert len(bulletins) > 0, "No bulletins found!"
    print(f"   -> Found {len(bulletins)} daily bulletins.")
    
    top = bulletins[0]
    print(f"   -> Top Bulletin: '{top['title'][:60]}...'")
    print(f"      Category: {top.get('category')} | Time: {top.get('published_time')}")
    print(f"      Is Important: {top.get('is_important')}")
    interp = top.get("interpretation", {})
    print(f"      Bias: {interp.get('bias')} ({interp.get('bias_badge')})")
    assert "bias" in interp, "Missing bias in interpretation!"
    assert "transmission_mechanism" in interp, "Missing transmission mechanism!"
    assert "intermarket_matrix" in interp, "Missing intermarket matrix!"
    assert "tactical_action" in interp, "Missing tactical action!"
    print("   -> Interpretation structure is complete and valid!")

    print("\n2. Testing FastAPI /api/daily-news and /api/daily-news/refresh...")
    client = TestClient(app)
    res = client.get("/api/daily-news")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data["status"] == "success", "Failed API status"
    print(f"   -> GET /api/daily-news returned {len(data['bulletins'])} items.")

    res_refresh = client.post("/api/daily-news/refresh")
    assert res_refresh.status_code == 200, f"Expected 200, got {res_refresh.status_code}"
    print(f"   -> POST /api/daily-news/refresh successfully refreshed bulletins!")

    print("\n3. Testing Breaking News Web State update...")
    scheduler.check_and_update_web_breaking_news()
    assert scheduler.latest_breaking_bulletin is not None, "latest_breaking_bulletin should not be None"
    print(f"   -> scheduler.latest_breaking_bulletin is active: '{scheduler.latest_breaking_bulletin['title'][:50]}...'")

    print("\n[SUCCESS] All Daily News & Breaking News Automation Tests PASSED!")

if __name__ == "__main__":
    test_daily_news()
