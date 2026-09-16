import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, HTTPException, Query, Request
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from runbooks import get_runbook, list_runbooks


app = FastAPI(
    title="AKS SRE Incident Collector",
    version="1.0.0",
)


INCIDENT_NAMESPACE = os.getenv(
    "INCIDENT_NAMESPACE",
    "sre",
)

WEBHOOK_TOKEN = os.getenv(
    "COLLECTOR_WEBHOOK_TOKEN",
    "",
)

AI_ANALYSER_URL = os.getenv(
    "AI_ANALYSER_URL",
    "http://ai-analyser:8080",
)

INCIDENT_DIR = Path(
    os.getenv(
        "INCIDENT_DIR",
        "/tmp/incidents",
    )
)

INCIDENT_STORAGE_ACCOUNT = os.getenv(
    "INCIDENT_STORAGE_ACCOUNT",
    "",
)

INCIDENT_STORAGE_CONTAINER = os.getenv(
    "INCIDENT_STORAGE_CONTAINER",
    "incidents",
)

def get_blob_container_client():
    """
    Create an Azure Blob container client using
    Azure Workload Identity / DefaultAzureCredential.
    """

    if not INCIDENT_STORAGE_ACCOUNT:
        raise RuntimeError(
            "INCIDENT_STORAGE_ACCOUNT is not configured"
        )

    account_url = (
        f"https://{INCIDENT_STORAGE_ACCOUNT}"
        ".blob.core.windows.net"
    )

    credential = DefaultAzureCredential()

    service_client = BlobServiceClient(
        account_url=account_url,
        credential=credential,
    )

    return service_client.get_container_client(
        INCIDENT_STORAGE_CONTAINER
    )

INCIDENT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    """
    Return the current UTC timestamp in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def save_incident(
    incident: dict[str, Any],
) -> str:
    """
    Persist an incident in Azure Blob Storage.
    """

    container_client = (
        get_blob_container_client()
    )

    blob_name = (
        f"{incident['incident_id']}.json"
    )

    blob_client = (
        container_client.get_blob_client(
            blob_name
        )
    )

    incident_json = json.dumps(
        incident,
        indent=2,
        default=str,
    )

    blob_client.upload_blob(
        incident_json.encode("utf-8"),
        overwrite=True,
    )

    return blob_name


def load_incident(
    incident_id: str,
) -> tuple[dict[str, Any], str]:
    """
    Load an incident from Azure Blob Storage.
    """

    container_client = (
        get_blob_container_client()
    )

    blob_name = (
        f"{incident_id}.json"
    )

    blob_client = (
        container_client.get_blob_client(
            blob_name
        )
    )

    try:
        downloaded = (
            blob_client.download_blob()
            .readall()
            .decode("utf-8")
        )

    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        ) from exc

    try:
        incident = json.loads(
            downloaded
        )

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Stored incident contains invalid JSON: "
                f"{exc}"
            ),
        ) from exc

    return incident, blob_name


def load_kubernetes_client() -> tuple[
    client.CoreV1Api,
    client.AppsV1Api,
]:
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


def extract_alert_context(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract useful information from the Azure Monitor
    Common Alert Schema.

    Supports both the Common Alert Schema and a basic
    fallback for non-common payloads.
    """

    data = payload.get(
        "data",
        {},
    )

    essentials = data.get(
        "essentials",
        {},
    )

    alert_context = data.get(
        "alertContext",
        {},
    )

    return {
        "alert_id": essentials.get(
            "alertId"
        ),
        "alert_rule": essentials.get(
            "alertRule"
        ),
        "severity": essentials.get(
            "severity"
        ),
        "monitor_condition": essentials.get(
            "monitorCondition"
        ),
        "signal_type": essentials.get(
            "signalType"
        ),
        "fired_date_time": essentials.get(
            "firedDateTime"
        ),
        "resolved_date_time": essentials.get(
            "resolvedDateTime"
        ),
        "affected_resource": essentials.get(
            "alertTargetIDs"
        ),
        "description": essentials.get(
            "description"
        ),
        "monitor_service": essentials.get(
            "monitorService"
        ),
        "expression": alert_context.get(
            "expression"
        ),
        "expression_value": alert_context.get(
            "expressionValue"
        ),
        "alert_for": alert_context.get(
            "for"
        ),
        "labels": alert_context.get(
            "labels",
            {},
        ),
        "annotations": alert_context.get(
            "annotations",
            {},
        ),
        "rule_group": alert_context.get(
            "ruleGroup"
        ),
    }


def collect_pods(
    core_api: client.CoreV1Api,
) -> list[dict[str, Any]]:
    """
    Collect pod state from the incident namespace.
    """

    pods = core_api.list_namespaced_pod(
        namespace=INCIDENT_NAMESPACE,
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
                        "restart_count": (
                            status.restart_count
                        ),
                        "state": (
                            status.state.to_dict()
                            if status.state
                            else None
                        ),
                    }
                    for status in (
                        pod.status.container_statuses
                        or []
                    )
                ],
            }
        )

    return result


def collect_events(
    core_api: client.CoreV1Api,
) -> list[dict[str, Any]]:
    """
    Collect Kubernetes events from the incident namespace.
    """

    events = core_api.list_namespaced_event(
        namespace=INCIDENT_NAMESPACE,
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
    """
    Collect the last 50 lines of logs from each pod.
    """

    logs: dict[str, str] = {}

    for pod in pods:
        pod_name = pod["name"]

        try:
            content = core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=INCIDENT_NAMESPACE,
                tail_lines=50,
            )

            logs[pod_name] = content

        except ApiException as exc:
            logs[pod_name] = (
                "Unable to collect logs: "
                f"HTTP {exc.status}: {exc.reason}"
            )

        except Exception as exc:
            logs[pod_name] = (
                f"Unable to collect logs: {exc}"
            )

    return logs


def collect_evidence() -> dict[str, Any]:
    """
    Collect Kubernetes evidence for the incident.
    """

    core_api, _ = load_kubernetes_client()

    pods = collect_pods(
        core_api
    )

    events = collect_events(
        core_api
    )

    logs = collect_logs(
        core_api,
        pods,
    )

    return {
        "namespace": INCIDENT_NAMESPACE,
        "collected_at": utc_now(),
        "pods": pods,
        "events": events,
        "logs": logs,
    }


def analyse_incident(
    incident: dict[str, Any],
) -> dict[str, Any]:
    """
    Send the collected incident context to the AI Analyser.
    """

    analyser_url = (
        f"{AI_ANALYSER_URL.rstrip('/')}/analyse"
    )

    payload = {
        "incident_id": incident["incident_id"],
        "alert": incident.get(
            "alert",
            {},
        ),
        "evidence": incident.get(
            "evidence",
            {},
        ),
    }

    try:
        request = urllib.request.Request(
            analyser_url,
            data=json.dumps(
                payload,
                default=str,
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:
            response_body = (
                response.read()
                .decode("utf-8")
            )

        return json.loads(
            response_body
        )

    except urllib.error.HTTPError as exc:
        response_body = (
            exc.read().decode(
                "utf-8",
                errors="replace",
            )
        )

        return {
            "status": "failed",
            "error": (
                "AI Analyser returned HTTP "
                f"{exc.code}: {response_body}"
            ),
        }

    except Exception as exc:
        return {
            "status": "failed",
            "error": (
                f"Unable to analyse incident: {exc}"
            ),
        }


def wait_for_sre_api_rollout(
    timeout_seconds: int = 120,
    poll_interval_seconds: int = 5,
) -> dict[str, Any]:
    """
    Wait for the sre-api Deployment rollout to complete.
    """

    _, apps_api = load_kubernetes_client()

    deployment_name = "sre-api"
    start_time = time.monotonic()

    while (
        time.monotonic() - start_time
        < timeout_seconds
    ):
        try:
            deployment = (
                apps_api.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=INCIDENT_NAMESPACE,
                )
            )

            desired_replicas = (
                deployment.spec.replicas or 0
            )

            status = (
                deployment.status
            )

            updated_replicas = (
                status.updated_replicas or 0
            )

            available_replicas = (
                status.available_replicas or 0
            )

            unavailable_replicas = (
                status.unavailable_replicas or 0
            )

            observed_generation = (
                status.observed_generation or 0
            )

            deployment_generation = (
                deployment.metadata.generation or 0
            )

            rollout_complete = (
                observed_generation
                >= deployment_generation
                and updated_replicas
                == desired_replicas
                and available_replicas
                == desired_replicas
                and unavailable_replicas
                == 0
            )

            if rollout_complete:
                return {
                    "success": True,
                    "deployment": deployment_name,
                    "desired_replicas": desired_replicas,
                    "updated_replicas": updated_replicas,
                    "available_replicas": available_replicas,
                    "unavailable_replicas": unavailable_replicas,
                    "observed_generation": (
                        observed_generation
                    ),
                    "generation": (
                        deployment_generation
                    ),
                }

        except ApiException as exc:
            return {
                "success": False,
                "error": (
                    "Unable to check rollout status: "
                    f"HTTP {exc.status}: {exc.reason}"
                ),
            }

        time.sleep(
            poll_interval_seconds
        )

    return {
        "success": False,
        "error": (
            "sre-api rollout did not complete "
            f"within {timeout_seconds} seconds"
        ),
    }


def verify_sre_api() -> dict[str, Any]:
    """
    Verify the application after remediation.
    """

    verification_url = (
        "http://sre-api:8000"
    )

    results: dict[str, Any] = {}

    endpoints = {
        "healthz": "/healthz",
        "readyz": "/readyz",
        "demo": "/demo",
    }

    for name, path in endpoints.items():
        url = (
            f"{verification_url}{path}"
        )

        try:
            request = urllib.request.Request(
                url,
                method="GET",
            )

            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                body = (
                    response.read()
                    .decode("utf-8")
                )

                results[name] = {
                    "status_code": response.status,
                    "body": body,
                }

        except urllib.error.HTTPError as exc:
            body = (
                exc.read()
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

            results[name] = {
                "status_code": exc.code,
                "body": body,
            }

        except Exception as exc:
            results[name] = {
                "status_code": None,
                "error": str(exc),
            }

    success = (
        results["healthz"].get(
            "status_code"
        ) == 200
        and results["readyz"].get(
            "status_code"
        ) == 200
        and results["demo"].get(
            "status_code"
        ) == 200
    )

    return {
        "success": success,
        "endpoints": results,
    }


@app.get("/runbooks")
def get_runbooks() -> dict[str, Any]:
    """
    Return the registered remediation runbooks.
    """

    return {
        "runbooks": list_runbooks()
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """
    Collector health endpoint.
    """

    return {
        "status": "healthy"
    }


@app.post("/alerts")
async def receive_alert(
    request: Request,
    token: str | None = Query(
        default=None
    ),
) -> dict[str, Any]:
    """
    Receive Azure Monitor Action Group webhook payload.
    """

    if WEBHOOK_TOKEN:
        if (
            not token
            or not hmac.compare_digest(
                token,
                WEBHOOK_TOKEN,
            )
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

    incident_id = str(
        uuid.uuid4()
    )

    alert = extract_alert_context(
        payload
    )

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
        "status": "Open",
        "alert": alert,
        "evidence": evidence,
        "approval": {
            "status": "Pending",
            "approved_by": None,
            "approved_at": None,
        },
        "remediation": {
            "status": "NotStarted",
            "runbook": None,
            "started_at": None,
            "completed_at": None,
            "result": None,
        },
    }

    ai_analysis = analyse_incident(
        incident
    )

    incident["ai_analysis"] = (
        ai_analysis
    )

    if ai_analysis.get(
        "status"
    ) == "failed":
        incident["status"] = (
            "AnalysisFailed"
        )
    else:
        incident["status"] = (
            "ApprovalPending"
        )

    incident_blob = save_incident(
    incident
        )

    return {
        "status": "accepted",
        "incident_id": incident_id,
        "alert_rule": alert.get(
            "alert_rule"
        ),
        "monitor_condition": alert.get(
            "monitor_condition"
        ),
        "incident_blob": incident_blob,
        "ai_analysis_status": (
            "completed"
            if ai_analysis.get(
                "status"
            ) != "failed"
            else "failed"
        ),
        "ai_analysis": ai_analysis,
    }


@app.get("/incidents/{incident_id}")
def get_incident(
    incident_id: str,
) -> dict[str, Any]:
    """
    Return a stored incident.
    """

    incident, _ = load_incident(
        incident_id
    )

    return incident


@app.post(
    "/incidents/{incident_id}/approve"
)
async def approve_incident(
    incident_id: str,
    request: Request,
) -> dict[str, Any]:
    """
    Approve an incident for future remediation.

    Existing behavior is preserved:
      - approved_by is still required.
      - If runbook is not supplied, restart-sre-api is used.
      - Approval does not execute remediation.
    """

    incident, _ = load_incident(
        incident_id
    )

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    approved_by = payload.get(
        "approved_by"
    )

    if not approved_by:
        raise HTTPException(
            status_code=400,
            detail="approved_by is required",
        )

    current_status = incident.get(
        "status",
        "Open",
    )

    if current_status not in {
        "ApprovalPending",
        "AnalysisFailed",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Incident cannot be approved "
                f"from status '{current_status}'"
            ),
        )

    # Existing approval payloads that do not specify a
    # runbook continue to use the current restart behavior.
    runbook_name = payload.get(
        "runbook",
        "restart-sre-api",
    )

    parameters = payload.get(
        "parameters",
        {},
    )

    if not isinstance(
        parameters,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail="parameters must be an object",
        )

    core_api, apps_api = (
        load_kubernetes_client()
    )

    try:
        runbook = get_runbook(
            name=runbook_name,
            core_api=core_api,
            apps_api=apps_api,
            namespace=INCIDENT_NAMESPACE,
            utc_now=utc_now,
            wait_for_rollout=wait_for_sre_api_rollout,
            verify_sre_api=verify_sre_api,
        )

        runbook.validate_parameters(
            parameters
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    approved_at = utc_now()

    incident["status"] = "Approved"

    incident["approval"] = {
        "status": "Approved",
        "approved_by": approved_by,
        "approved_at": approved_at,
        "runbook": runbook_name,
        "parameters": parameters,
    }

    # Keep the remediation structure compatible with
    # the existing incident schema while recording the
    # selected runbook and parameters.
    incident["remediation"] = {
        "status": "NotStarted",
        "runbook": runbook_name,
        "parameters": parameters,
        "started_at": None,
        "completed_at": None,
        "result": None,
    }

    save_incident(
        incident
    )

    return {
        "status": "approved",
        "incident_id": incident_id,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "runbook": runbook_name,
        "parameters": parameters,
    }


@app.post(
    "/incidents/{incident_id}/remediate"
)
def remediate_incident(
    incident_id: str,
) -> dict[str, Any]:
    """
    Execute the runbook that was explicitly recorded
    in the incident approval.

    The endpoint does not accept a runbook from the caller.
    The approved runbook is the only runbook that can execute.
    """

    incident, _ = load_incident(
        incident_id
    )

    current_status = incident.get(
        "status",
        "Open",
    )

    if current_status != "Approved":
        raise HTTPException(
            status_code=409,
            detail=(
                "Incident must be Approved "
                "before remediation. "
                f"Current status: {current_status}"
            ),
        )

    remediation = incident.get(
        "remediation",
        {},
    )

    if remediation.get(
        "status"
    ) == "Succeeded":
        raise HTTPException(
            status_code=409,
            detail="Remediation already completed",
        )

    approval = incident.get(
        "approval",
        {},
    )

    # New incidents store the runbook in approval.
    # These fallbacks preserve compatibility with
    # older incidents created before runbook selection
    # was added.
    runbook_name = approval.get(
        "runbook"
    ) or remediation.get(
        "runbook"
    ) or "restart-sre-api"

    parameters = approval.get(
        "parameters"
    )

    if parameters is None:
        parameters = remediation.get(
            "parameters",
            {},
        )

    if not isinstance(
        parameters,
        dict,
    ):
        parameters = {}

    core_api, apps_api = (
        load_kubernetes_client()
    )

    try:
        runbook = get_runbook(
            name=runbook_name,
            core_api=core_api,
            apps_api=apps_api,
            namespace=INCIDENT_NAMESPACE,
            utc_now=utc_now,
            wait_for_rollout=wait_for_sre_api_rollout,
            verify_sre_api=verify_sre_api,
        )

        # Validate again immediately before execution.
        runbook.validate_parameters(
            parameters
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    started_at = utc_now()

    remediation["status"] = "Running"
    remediation["runbook"] = runbook_name
    remediation["parameters"] = parameters
    remediation["started_at"] = started_at
    remediation["completed_at"] = None
    remediation["result"] = None

    incident["remediation"] = remediation

    save_incident(
        incident
    )

    try:
        result = runbook.execute(
            parameters
        )

        if result.get(
            "success"
        ):
            incident["status"] = (
                "Remediated"
            )

            incident["remediation"] = {
                "status": "Succeeded",
                "runbook": runbook_name,
                "parameters": parameters,
                "started_at": started_at,
                "completed_at": utc_now(),
                "result": result,
            }

        else:
            incident["status"] = (
                "RemediationFailed"
            )

            incident["remediation"] = {
                "status": "Failed",
                "runbook": runbook_name,
                "parameters": parameters,
                "started_at": started_at,
                "completed_at": utc_now(),
                "result": result,
            }

    except Exception as exc:
        incident["status"] = (
            "RemediationFailed"
        )

        incident["remediation"] = {
            "status": "Failed",
            "runbook": runbook_name,
            "parameters": parameters,
            "started_at": started_at,
            "completed_at": utc_now(),
            "result": {
                "success": False,
                "error": str(exc),
            },
        }

    save_incident(
        incident
    )

    return {
        "incident_id": incident_id,
        "status": incident["status"],
        "remediation": incident[
            "remediation"
        ],
    }