from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_healthz():
    r = client.get('/healthz')
    assert r.status_code == 200


def test_receives_alert(monkeypatch):
    monkeypatch.setattr(main, 'query_logs', lambda q: [{"LogMessage": "failure"}])
    monkeypatch.setattr(main, 'query_prometheus', lambda: {"error_rate": 0.2})
    monkeypatch.setattr(main, 'get_k8s_events', lambda ns, workload: [{"reason": "BackOff"}])

    class Dummy:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"status": "analysis-created"}

    monkeypatch.setattr(main.httpx, 'post', lambda *a, **k: Dummy())
    r = client.post('/api/v1/alerts', json={"alert_name":"High5xx","workload":"sre-api"})
    assert r.status_code == 200
    assert r.json()["analysis"]["status"] == "analysis-created"
