from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def setup_function():
    main.FAILURE_MODE = False


def test_healthz():
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json()['status'] == 'healthy'


def test_failure_mode_changes_readiness_and_demo():
    client.post('/admin/failure-mode', json={'enabled': True})
    assert client.get('/readyz').status_code == 503
    assert client.get('/demo').status_code == 500
    client.post('/admin/failure-mode', json={'enabled': False})
    assert client.get('/readyz').status_code == 200


def test_metrics_endpoint():
    r = client.get('/metrics')
    assert r.status_code == 200
    assert b'http_requests_total' in r.content
