from fastapi.testclient import TestClient

from app.main import app
from tests.test_actions_drafters import INS_001, INS_002

client = TestClient(app)


def test_draft_action_returns_a_grounded_draft():
    response = client.post("/internal/draft-action", json={"insight": INS_001, "type": "VENDOR_ESCALATION"})
    assert response.status_code == 200
    body = response.json()
    assert body["insight_id"] == "ins_001"
    assert body["type"] == "VENDOR_ESCALATION"
    assert body["facts_cited"]


def test_draft_action_rejects_inapplicable_type():
    response = client.post("/internal/draft-action", json={"insight": INS_002, "type": "VENDOR_ESCALATION"})
    assert response.status_code == 400


def test_draft_action_requires_an_insight_packet():
    response = client.post("/internal/draft-action", json={"type": "VENDOR_ESCALATION"})
    assert response.status_code == 400


def test_draft_action_requires_a_type():
    response = client.post("/internal/draft-action", json={"insight": INS_001})
    assert response.status_code == 400
