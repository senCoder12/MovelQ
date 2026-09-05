from fastapi.testclient import TestClient

from app.main import app
from tests.test_alert_router import _insight

client = TestClient(app)


def test_evaluate_alerts_returns_candidates_and_ranked_ids():
    insight = _insight("ins_001", "delay_reconciliation_gap", severity=92, n=215885, entity_id="ALL")
    response = client.post("/internal/evaluate-alerts", json={"insights": [insight], "known_entities": []})
    assert response.status_code == 200
    body = response.json()
    assert body["ranked_insight_ids"] == ["ins_001"]
    assert any(c["rule_id"] == "r_recon_critical" for c in body["candidates"])


def test_evaluate_alerts_dedupes_before_matching():
    weak = _insight("ins_a", "delay_reconciliation_gap", severity=40, n=215885)
    strong = _insight("ins_b", "delay_reconciliation_gap", severity=92, n=215885)
    response = client.post("/internal/evaluate-alerts", json={"insights": [weak, strong]})
    body = response.json()
    assert body["ranked_insight_ids"] == ["ins_b"]


def test_evaluate_alerts_respects_known_entities():
    insight = _insight("ins_001", "any_metric", severity=10, entity_id="ALL", entity_dim="fleet")
    seen = client.post(
        "/internal/evaluate-alerts", json={"insights": [insight], "known_entities": [["fleet", "ALL"]]}
    ).json()
    unseen = client.post("/internal/evaluate-alerts", json={"insights": [insight], "known_entities": []}).json()
    assert not any(c["rule_id"] == "r_new_bad_entity" for c in seen["candidates"])
    assert any(c["rule_id"] == "r_new_bad_entity" for c in unseen["candidates"])
