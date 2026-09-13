import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


app = FastAPI(
    title="AKS SRE Incident Collector",
    version="1.0.0",
)

INCIDENT_NAMESPACE = os.getenv("INCIDENT_NAMESPACE", "sre")
WEBHOOK_TOKEN = os.getenv("COLLECTOR_WEBHOOK_TOKEN", "")

INCIDENT_DIR = Path(
    os.getenv("INCIDENT_DIR", "/tmp/incidents")
)

INCIDENT_DIR.mkdir(parents=True, exist_ok=True)


def load_kubernetes_client() -> tuple[client.CoreV1Api, client.AppsV1Api]:
    """
    Load Kubernetes configuration.

    In AKS:
      use in-cluster configuration.

    During local development:
      fall back to kubeconfig.
    """
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return (
        client.CoreV1Api(),
        client.AppsV1Api(),
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_alert_context(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Extract useful information from the Azure Monitor
    Common Alert Schema.

    Supports both the Common Alert Schema and a basic
    fallback for non-common payloads.
    """

    data = payload.get("data", {})

    essentials = data.get("essentials", {})
    alert_context = data.get("alertContext", {})

    return {
        "alert_id": essentials.get("alertId"),
        "alert_rule": essentials.get("alertRule"),
        "severity": essentials.get("severity"),
        "monitor_condition": essentials.get("monitorCondition"),
        "signal_type": essentials.get("signalType"),
        "fired_date_time": essentials.get("firedDateTime"),
        "resolved_date_time": essentials.get("resolvedDateTime"),
        "affected_resource": essentials.get("alertTargetIDs"),
        "description": essentials.get("description"),
        "monitor_service": essentials.get("monitorService"),
        "expression": alert_context.get("expression"),
        "expression_value": alert_context.get("expressionValue"),
        "alert_for": alert_context.get("for"),
        "labels": alert_context.get("labels", {}),
        "annotations": alert_context.get("annotations", {}),
        "rule_group": alert_context.get("ruleGroup"),
    }


def collect_pods(
    core_api: client.CoreV1Api,
) -> list[dict[str, Any]]:
    pods = core_api.list_namespaced_pod(
        namespace=INCIDENT_NAMESPACE
    )

    result: list[dict[str, Any]] = []

    for pod in pods.items:
        result.append(
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "pod_ip": pod.status.pod_ip,
                "node_name": pod.spec.node_name,
                "start_time": (
                    pod.status.start_time.isoformat()
                    if pod.status.start_time
                    else None
                ),
                "container_statuses": [
                    {
                        "name": status.name,
                        "ready": status.ready,
                        "restart_count": status.restart_count,
                        "state": (
                            status.state.to_dict()
                            if status.state
                            else None
                        ),
                    }
                    for status in (pod.status.container_statuses or [])
                ],
            }
        )

    return result


def collect_events(
    core_api: client.CoreV1Api,
) -> list[dict[str, Any]]:
    events = core_api.list_namespaced_event(
        namespace=INCIDENT_NAMESPACE
    )

    result: list[dict[str, Any]] = []

    for event in events.items:
        result.append(
            {
                "name": event.metadata.name,
                "reason": event.reason,
                "message": event.message,
                "type": event.type,
                "count": event.count,
                "first_timestamp": (
                    event.first_timestamp.isoformat()
                    if event.first_timestamp
                    else None
                ),
                "last_timestamp": (
                    event.last_timestamp.isoformat()
                    if event.last_timestamp
                    else None
                ),
                "involved_object": {
                    "kind": (
                        event.involved_object.kind
                        if event.involved_object
                        else None
                    ),
                    "name": (
                        event.involved_object.name
                        if event.involved_object
                        else None
                    ),
                },
            }
        )

    return result


def collect_logs(
    core_api: client.CoreV1Api,
    pods: list[dict[str, Any]],
) -> dict[str, str]:
    logs: dict[str, str] = {}

    for pod in pods:
        pod_name = pod["name"]

        try:
            content = core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=INCIDENT_NAMESPACE,
                tail_lines=200,
            )

            logs[pod_name] = content

        except ApiException as exc:
            logs[pod_name] = (
                f"Unable to collect logs: "
                f"HTTP {exc.status}: {exc.reason}"
            )
        except Exception as exc:
            logs[pod_name] = (
                f"Unable to collect logs: {exc}"
            )

    return logs


def collect_evidence() -> dict[str, Any]:
    core_api, _ = load_kubernetes_client()

    pods = collect_pods(core_api)
    events = collect_events(core_api)
    logs = collect_logs(core_api, pods)

    return {
        "namespace": INCIDENT_NAMESPACE,
        "collected_at": utc_now(),
        "pods": pods,
        "events": events,
        "logs": logs,
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/alerts")
async def receive_alert(
    request: Request,
    token: str | None = Query(default=None),
) -> dict[str, Any]:
    """
    Receive Azure Monitor Action Group webhook payload.
    """

    if WEBHOOK_TOKEN:
        if not token or not hmac.compare_digest(
            token,
            WEBHOOK_TOKEN,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook token",
            )

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    incident_id = str(uuid.uuid4())

    alert = extract_alert_context(payload)

    try:
        evidence = collect_evidence()
    except Exception as exc:
        evidence = {
            "collection_error": str(exc),
            "collected_at": utc_now(),
        }

    incident = {
        "incident_id": incident_id,
        "received_at": utc_now(),
        "alert": alert,
        "evidence": evidence,
    }

    incident_file = INCIDENT_DIR / f"{incident_id}.json"

    incident_file.write_text(
        json.dumps(
            incident,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return {
        "status": "accepted",
        "incident_id": incident_id,
        "alert_rule": alert.get("alert_rule"),
        "monitor_condition": alert.get(
            "monitor_condition"
        ),
        "incident_file": str(incident_file),
    }


@app.get("/incidents/{incident_id}")
def get_incident(
    incident_id: str,
) -> dict[str, Any]:

    incident_file = (
        INCIDENT_DIR / f"{incident_id}.json"
    )

    if not incident_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    return json.loads(
        incident_file.read_text(
            encoding="utf-8"
        )
    )