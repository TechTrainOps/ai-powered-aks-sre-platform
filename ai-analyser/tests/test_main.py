from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_healthz():
    assert client.get('/healthz').status_code == 200


def test_analysis_fallback_and_approval(monkeypatch):
    monkeypatch.setattr(main, 'client', None)
    payload = {
        "incident_id": "INC-TEST",
        "alert": {"alert_name": "High5xx", "severity": "Sev2", "description": "High error rate"},
        "logs": [{"message": "request failed"}],
        "metrics": {"error_rate": 0.3},
        "events": [{"type": "Warning", "reason": "BackOff"}],
    }
    r = client.post('/api/v1/analyse', json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "PENDING_APPROVAL"
    r = client.post('/api/v1/incidents/INC-TEST/approve', json={"approved_by": "engineer@example.com", "comment": "Reviewed"})
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"
