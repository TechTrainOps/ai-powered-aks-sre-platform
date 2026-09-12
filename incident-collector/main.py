import os
import re
import uuid
from datetime import timedelta
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from fastapi import FastAPI, HTTPException
from kubernetes import client, config
from pydantic import BaseModel, Field

app = FastAPI(title="Incident Collector", version="1.0.0")

LOG_WORKSPACE_ID = os.getenv("LOG_WORKSPACE_ID", "")
AI_ANALYSER_URL = os.getenv("AI_ANALYSER_URL", "http://ai-analyser:8080")
PROMETHEUS_QUERY_URL = os.getenv("PROMETHEUS_QUERY_URL", "")
PROMETHEUS_BEARER_TOKEN = os.getenv("PROMETHEUS_BEARER_TOKEN", "")

credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
logs_client = LogsQueryClient(credential)

try:
    config.load_incluster_config()
except Exception:
    try:
        config.load_kube_config()
    except Exception:
        pass

core_api = client.CoreV1Api()


class AlertRequest(BaseModel):
    incident_id: str | None = None
    alert_name: str = "unknown-alert"
    severity: str = "Sev3"
    description: str = ""
    namespace: str = "sre"
    workload: str = "sre-api"
    labels: dict[str, str] = Field(default_factory=dict)


class Incident(BaseModel):
    incident_id: str
    alert: dict[str, Any]
    logs: list[dict[str, Any]]
    metrics: dict[str, Any]
    events: list[dict[str, Any]]


def query_logs(query: str) -> list[dict[str, Any]]:
    if not LOG_WORKSPACE_ID:
        return []
    try:
        response = logs_client.query_workspace(
            LOG_WORKSPACE_ID,
            query,
            timespan=timedelta(minutes=15),
        )
        if response.status != LogsQueryStatus.SUCCESS:
            return []
        rows = []
        for table in response.tables:
            for row in table.rows:
                rows.append(dict(zip(table.columns, row)))
        return rows[:100]
    except Exception:
        return []


def get_k8s_events(namespace: str, workload: str) -> list[dict[str, Any]]:
    try:
        events = core_api.list_namespaced_event(namespace=namespace).items
    except Exception:
        return []
    result = []
    for event in events:
        message = event.message or ""
        involved = getattr(event.involved_object, "name", "")
        if workload.lower() in involved.lower() or workload.lower() in message.lower():
            result.append({
                "type": event.type,
                "reason": event.reason,
                "message": message,
                "object": involved,
                "last_timestamp": str(event.last_timestamp or event.event_time or ""),
            })
    return result[-50:]


def query_prometheus() -> dict[str, Any]:
    if not PROMETHEUS_QUERY_URL:
        # Lab fallback: scrape the API's Prometheus exposition endpoint directly.
        # In the managed setup, set PROMETHEUS_QUERY_URL to a Prometheus-compatible
        # query endpoint and the collector will use PromQL instead.
        try:
            r = httpx.get("http://sre-api:8000/metrics", timeout=10)
            r.raise_for_status()
            text = r.text
            request_rate = 0.0
            error_rate = 0.0
            restarts = 0.0
            for line in text.splitlines():
                if line.startswith("http_requests_total") and 'status="5' in line:
                    try:
                        error_rate += float(line.rsplit(" ", 1)[-1])
                    except ValueError:
                        pass
                elif line.startswith("http_requests_total"):
                    try:
                        request_rate += float(line.rsplit(" ", 1)[-1])
                    except ValueError:
                        pass
            return {
                "source": "application_metrics_fallback",
                "request_total_seen": request_rate,
                "error_total_seen": error_rate,
                "pod_restarts": restarts,
            }
        except Exception as exc:
            return {"source": "fallback_error", "error": str(exc)}
    headers = {}
    if PROMETHEUS_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {PROMETHEUS_BEARER_TOKEN}"
    queries = {
        "request_rate": "sum(rate(http_requests_total[5m]))",
        "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m]))',
    }
    result = {}
    for key, promql in queries.items():
        try:
            r = httpx.get(PROMETHEUS_QUERY_URL, params={"query": promql}, headers=headers, timeout=10)
            r.raise_for_status()
            result[key] = r.json()
        except Exception as exc:
            result[key] = {"error": str(exc)}
    return result


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}


@app.post("/api/v1/alerts")
def receive_alert(alert: AlertRequest):
    incident_id = alert.incident_id or f"INC-{uuid.uuid4().hex[:8].upper()}"
    workload = re.sub(r"[^A-Za-z0-9._-]", "", alert.workload)
    log_query = f'''ContainerLogV2 | where TimeGenerated > ago(15m) | where LogMessage has "{workload}" or ContainerName has "{workload}" | project TimeGenerated, ContainerName, LogMessage | order by TimeGenerated desc'''
    evidence = Incident(
        incident_id=incident_id,
        alert=alert.model_dump(),
        logs=query_logs(log_query),
        metrics=query_prometheus(),
        events=get_k8s_events(alert.namespace, workload),
    )

    try:
        response = httpx.post(
            f"{AI_ANALYSER_URL}/api/v1/analyse",
            json=evidence.model_dump(),
            timeout=60,
        )
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI analyser call failed: {exc}") from exc

    return {"incident_id": incident_id, "analysis": response.json()}
