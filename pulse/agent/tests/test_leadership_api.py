from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAYLOAD = {
    "period": "July 2026",
    "tiles": [{"label": "Trips analysed", "value": "215,885", "reference": "July 2026", "direction": "neutral"}],
    "findings": [
        {
            "insight_id": "ins_001",
            "severity": 92,
            "title": "117,605 trips arrived late while reporting zero delay",
            "metric": {"id": "delay_reconciliation_gap", "name": "Delay reconciliation gap", "value": 54.5, "unit": "%", "n": 215885},
        }
    ],
    "footer": {"computed_from_trips": 215885, "excluded_trips": 0, "excluded_pct": 0.0, "exclusion_reasons": []},
}


def test_leadership_narrative_falls_back_without_an_llm_key():
    # No LLM_API_KEY is configured in the test environment, so this must
    # degrade to the template fallback rather than 500 or hang on a real call.
    response = client.post("/internal/leadership-narrative", json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert "215,885" in body["headline"] or "215,885" in body["summary"]
    assert body["findings"][0]["insight_id"] == "ins_001"
    assert body["findings"][0]["recommendation"]


def test_leadership_narrative_is_cached_on_identical_payload():
    first = client.post("/internal/leadership-narrative", json=PAYLOAD).json()
    second = client.post("/internal/leadership-narrative", json=PAYLOAD).json()
    assert first == second
