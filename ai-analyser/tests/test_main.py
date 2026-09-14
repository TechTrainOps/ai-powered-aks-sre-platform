from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_healthz():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyse_missing_incident_id():
    response = client.post(
        "/analyse",
        json={
            "alert": {},
            "evidence": {},
        },
    )

    assert response.status_code == 422


def test_analyse_invalid_incident_payload():
    response = client.post(
        "/analyse",
        json={
            "incident_id": "",
            "alert": {},
            "evidence": {},
        },
    )

    assert response.status_code == 422