from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_healthz():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_alert_endpoint():
    payload = {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "test-alert",
                "alertRule": "SREApiHighErrorRate",
                "severity": "Sev2",
                "monitorCondition": "Fired",
                "signalType": "Metric",
                "monitorService": "Prometheus",
                "description": "Test alert",
            },
            "alertContext": {
                "expression": "test_expression > 5",
                "expressionValue": "10",
                "for": "PT5M",
                "labels": {
                    "service": "sre-api",
                    "namespace": "sre",
                },
                "annotations": {
                    "summary": "Test alert",
                },
            },
        },
    }

    response = client.post(
        "/alerts",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "accepted"
    assert body["alert_rule"] == "SREApiHighErrorRate"