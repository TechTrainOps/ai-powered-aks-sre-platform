````markdown
# Incident Response

## 1. Purpose

This document describes how the **AI-Powered AKS SRE & Incident Automation Platform** detects, analyzes, approves, remediates, and records application incidents running on Azure Kubernetes Service (AKS).

The incident response workflow is designed around:

```text
Detect
  ↓
Collect Evidence
  ↓
Analyse
  ↓
Human Approval
  ↓
Remediate
  ↓
Verify
  ↓
Record
````

The AI layer assists with root cause analysis, while Kubernetes changes are performed only through an approved remediation runbook.

---

# 2. Incident Response Architecture

The incident response path is:

```text
                    +----------------------+
                    |     sre-api          |
                    |     FastAPI          |
                    +----------+-----------+
                               |
                               | Prometheus metrics
                               v
                    +----------------------+
                    | Azure Managed        |
                    | Prometheus           |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Azure Monitor        |
                    | Prometheus Alert     |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Action Group         |
                    | Email + Webhook      |
                    +----------+-----------+
                               |
                               | Webhook
                               v
                    +----------------------+
                    | Incident Collector   |
                    +----------+-----------+
                               |
               +---------------+---------------+
               |               |               |
               v               v               v
        Kubernetes API      Pod Logs       K8s Events
               |               |               |
               +---------------+---------------+
                               |
                               v
                    +----------------------+
                    | Structured Incident  |
                    | Evidence              |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | AI Analyser           |
                    | Azure OpenAI          |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | AI-assisted RCA       |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Human Approval        |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Approved Runbook      |
                    +----------+-----------+
                               |
                +--------------+--------------+
                |              |              |
                v              v              v
             Restart         Scale         Rollback
                |              |              |
                +--------------+--------------+
                               |
                               v
                    +----------------------+
                    | Kubernetes           |
                    | Remediation          |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Rollout & Application |
                    | Health Verification   |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Incident Record       |
                    | Azure Blob Storage    |
                    +----------------------+
```

---

# 3. Detection

The incident response process begins with application telemetry.

The `sre-api` application exposes Prometheus metrics through:

```text
/metrics
```

Important application metrics include:

```text
http_requests_total
http_request_duration_seconds
```

The application metrics are collected through **Azure Managed Prometheus**.

Azure Monitor evaluates the Prometheus alert rule.

---

# 4. High 5xx Error Rate Alert

The primary incident scenario implemented in this project is a sustained HTTP 5xx error rate.

The alert expression is:

```text
100 *
(
  sum(rate(http_requests_total{namespace="sre",status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{namespace="sre"}[5m]))
) > 5
```

The alert configuration is:

```text
Threshold:  > 5%
Duration:   5 minutes
Severity:   Sev2
```

The alert therefore represents a sustained error condition rather than a single failed request.

The alert is associated with an Azure Monitor Action Group.

The Action Group sends:

```text
Email notification
Webhook notification
```

---

# 5. Alert Delivery

The Action Group sends the webhook request to:

```text
Incident Collector
```

The Incident Collector exposes:

```text
POST /alerts
```

The webhook request is authenticated using the configured collector webhook token.

The collector validates the incoming request before processing the alert.

The alert payload is used to populate the incident context.

---

# 6. Incident Creation

When a valid alert is received, the Incident Collector creates an incident record.

The incident contains information such as:

```json
{
  "incident_id": "...",
  "received_at": "...",
  "status": "Open",
  "alert": {},
  "evidence": {},
  "approval": {
    "status": "Pending",
    "approved_by": null,
    "approved_at": null
  },
  "remediation": {
    "status": "NotStarted",
    "runbook": null,
    "started_at": null,
    "completed_at": null,
    "result": null
  }
}
```

The Incident Collector then gathers operational evidence and sends the incident context to the AI Analyser.

---

# 7. Evidence Collection

The Incident Collector collects Kubernetes evidence from the AKS cluster.

The evidence collection process includes:

```text
Incident Collector
       |
       +---- Pods
       |
       +---- Pod Logs
       |
       +---- Kubernetes Events
       |
       +---- Deployment
       |
       +---- ReplicaSets
       |
       v
Structured Incident Evidence
```

The collected evidence includes information such as:

```text
Pod name
Pod status
Ready state
Restart count
Container state
Container image
Deployment replica count
Available replicas
Deployment revision
Pod logs
Kubernetes events
```

The Collector uses the Kubernetes Python client to query the cluster.

---

# 8. Example Evidence

For a readiness failure, the evidence can show:

```text
Pod state:
Running

Readiness:
False

Restart count:
0

/healthz:
HTTP 200

/readyz:
HTTP 503

Kubernetes event:
HTTP probe failed with status code 503
```

This distinction is important because a pod can remain alive while failing its readiness check.

---

# 9. AI-Assisted Root Cause Analysis

After collecting evidence, the Incident Collector sends the incident context to the AI Analyser.

The communication flow is:

```text
Incident Collector
       |
       | Incident context
       v
AI Analyser
       |
       v
Azure OpenAI
       |
       v
Structured RCA
       |
       v
Incident Collector
```

The AI analysis contains information such as:

```json
{
  "incident_id": "...",
  "summary": "...",
  "root_cause": "...",
  "confidence": 0.78,
  "severity": "Sev2",
  "evidence": [],
  "recommended_action": "..."
}
```

The analysis is used to assist the engineer in understanding the incident.

The AI output does not directly execute Kubernetes changes.

---

# 10. AI Analysis Example

During the controlled readiness failure test, the AI analysis identified:

```text
Summary:
The sre-api service experienced a high 5xx error rate while its pods
were running but not ready, with readiness probes repeatedly returning 503.

Root Cause:
The most likely root cause was readiness failure while the application
pods remained running.

Evidence:
- Elevated 5xx error rate
- Pods Running but NotReady
- Readiness endpoint returning HTTP 503
- Health endpoint remaining HTTP 200
- Kubernetes readiness probe failures
- No crash loop or pod restart behavior
```

The analysis produced a confidence value and severity classification.

The AI response is treated as an engineering aid and remains subject to human review.

---

# 11. Approval State

After successful AI analysis, the incident waits for human approval.

The incident enters:

```text
ApprovalPending
```

The approval API is:

```text
POST /incidents/{incident_id}/approve
```

The approval request contains:

```json
{
  "runbook": "restart-sre-api",
  "parameters": {},
  "approved_by": "operator"
}
```

After successful approval:

```text
approval.status = Approved
```

The incident stores:

```text
approved_by
approved_at
runbook
parameters
```

---

# 12. Human-in-the-Loop Design

The approval boundary is intentional:

```text
AI Analysis
     |
     v
Recommended Action
     |
     v
Human Review
     |
     v
Approved Runbook
     |
     v
Remediation
```

The AI analyser does not directly call Kubernetes remediation APIs.

The human operator decides which registered runbook is approved for execution.

This keeps the execution path deterministic and auditable.

---

# 13. Runbook Execution

After approval, remediation is triggered through:

```text
POST /incidents/{incident_id}/remediate
```

The remediation API loads the approved runbook and its parameters from the incident.

The remediation request does not provide a new arbitrary runbook at execution time.

The runbook must already be approved and associated with the incident.

The runbook registry currently contains:

```text
restart-sre-api
scale-sre-api
rollback-sre-api
```

---

# 14. Restart Incident Response

The restart runbook is used when restarting the application Deployment is the approved remediation.

The workflow is:

```text
Approved Incident
       |
       v
restart-sre-api
       |
       v
Read Deployment
       |
       v
Patch pod-template annotation
       |
       v
New Deployment revision
       |
       v
New ReplicaSet / Pods
       |
       v
Rollout verification
       |
       v
Application health verification
```

The remediation uses the annotation:

```text
sre.azure.com/remediation-restarted-at
```

The runbook verifies:

```text
Desired replicas
Updated replicas
Available replicas
Unavailable replicas
```

It then verifies:

```text
/healthz
/readyz
/demo
```

---

# 15. Scale Incident Response

The scale runbook is used when the number of application replicas needs to be changed.

The workflow is:

```text
Approved Incident
       |
       v
scale-sre-api
       |
       v
Validate parameters
       |
       v
Patch Deployment replicas
       |
       v
Kubernetes reconciliation
       |
       v
Verify requested replica count
       |
       v
Verify replica availability
       |
       v
Verify application health
```

The runbook supports:

```text
1 <= replicas <= 5
```

The runbook explicitly verifies that Kubernetes reaches the requested replica count.

It does not treat a successful Kubernetes PATCH request alone as successful remediation.

---

# 16. Rollback Incident Response

The rollback runbook restores the immediately previous Deployment revision.

The workflow is:

```text
Approved Incident
       |
       v
rollback-sre-api
       |
       v
Read current Deployment
       |
       v
Read current revision
       |
       v
List ReplicaSets
       |
       v
Find previous revision
       |
       v
Read previous pod template
       |
       v
Patch Deployment
       |
       v
Rollout verification
       |
       v
Verify target image
       |
       v
Application health verification
```

The rollback target is derived from Kubernetes Deployment history.

The approval request does not specify an arbitrary image.

This keeps rollback tied to a known previous Deployment revision.

---

# 17. Remediation Verification

Every remediation path performs post-action verification.

The basic verification model is:

```text
Kubernetes Change
       |
       v
Rollout Verification
       |
       v
Application Verification
       |
       +---- /healthz
       |
       +---- /readyz
       |
       +---- /demo
```

A remediation is considered successful only when the runbook's required rollout and application checks pass.

For `sre-api`, successful verification requires:

```text
/healthz -> HTTP 200
/readyz  -> HTTP 200
/demo    -> HTTP 200
```

---

# 18. Incident State

The incident stores analysis, approval, and remediation information.

A successful incident typically progresses through:

```text
Open
  |
  v
AI Analysis
  |
  v
ApprovalPending
  |
  v
Approved
  |
  v
Remediation
  |
  v
Remediated
```

The remediation section records:

```text
status
runbook
parameters
started_at
completed_at
result
```

Failure scenarios can result in states such as:

```text
AnalysisFailed
RemediationFailed
VerificationFailed
```

The exact incident status depends on which stage of the workflow fails.

---

# 19. Incident Persistence

Incident data is persisted in Azure Blob Storage.

The storage layout is:

```text
incidents/
    |
    +-- <incident-id>.json
```

The stored incident includes:

```json
{
  "incident_id": "...",
  "received_at": "...",
  "status": "...",
  "alert": {},
  "evidence": {},
  "ai_analysis": {},
  "approval": {},
  "remediation": {}
}
```

This allows incident state and remediation results to remain available independently of pod or Deployment lifecycle.

---

# 20. Incident Retrieval

An incident can be retrieved through:

```text
GET /incidents/{incident_id}
```

This returns the current incident state, including:

```text
Alert information
Evidence
AI analysis
Approval
Remediation
```

The API therefore provides a single view of the incident lifecycle.

---

# 21. Controlled Fault Injection

The project includes an application-level failure mode for repeatable incident testing.

The API is:

```text
POST /admin/failure-mode
```

Enable the failure mode:

```json
{
  "enabled": true
}
```

When enabled:

```text
/readyz -> HTTP 503
/demo   -> HTTP 500
```

The application process remains running.

This creates a controlled incident where:

```text
Pod status:
Running

Pod readiness:
NotReady
```

This is useful for validating monitoring and remediation without introducing an actual software defect.

---

# 22. Controlled Incident Example

The final restart test followed this sequence:

```text
1. Application failure mode enabled
        |
        v
2. Both sre-api pods became NotReady
        |
        v
3. Readiness probes returned HTTP 503
        |
        v
4. HTTP 5xx error rate increased
        |
        v
5. Azure Monitor alert fired
        |
        v
6. Incident Collector received webhook
        |
        v
7. Kubernetes evidence was collected
        |
        v
8. AI-assisted RCA was generated
        |
        v
9. Human approved restart-sre-api
        |
        v
10. Restart runbook executed
        |
        v
11. New Deployment revision created
        |
        v
12. 2/2 replicas became available
        |
        v
13. /healthz returned 200
        |
        v
14. /readyz returned 200
        |
        v
15. /demo returned 200
        |
        v
16. Remediation marked Succeeded
```

The final restart test used application image:

```text
sre-api:715
```

The Deployment moved from revision `34` to revision `35`.

The restart operation recorded:

```text
sre.azure.com/remediation-restarted-at
```

with the time at which remediation began.

The final remediation result was:

```text
success = true
rollout.success = true
verification.success = true
```

---

# 23. Rollback Incident Example

The rollback workflow was also tested using a controlled application failure.

The tested sequence was:

```text
sre-api:713
      |
      v
Controlled application failure
      |
      v
High 5xx alert
      |
      v
Incident created
      |
      v
AI analysis
      |
      v
Human approval
      |
      v
rollback-sre-api
      |
      v
Previous revision identified
      |
      v
sre-api:712
      |
      v
Rollout completed
      |
      v
healthz = 200
readyz  = 200
demo    = 200
```

The rollback mechanism therefore validated both revision discovery and post-rollback health verification.

---

# 24. Scale Incident Example

A controlled scale remediation was tested using:

```text
Previous replicas: 2
Requested replicas: 3
Observed replicas: 3
Available replicas: 3
```

The scale remediation completed successfully and application verification returned:

```text
healthz = 200
readyz  = 200
demo    = 200
```

The HPA was then restored to:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

---

# 25. Safe Failure Handling

The remediation workflow is designed to fail explicitly when an operation cannot be verified.

Examples include:

```text
Invalid runbook
Invalid parameters
Kubernetes API failure
Replica count mismatch
Rollout timeout
Target revision unavailable
Target image mismatch
Application health verification failure
```

A failed remediation should not be treated as successful merely because the initial Kubernetes API request was accepted.

The runbooks return structured results so that the incident record can capture the failure.

---

# 26. RBAC During Incident Response

The Incident Collector uses a dedicated Kubernetes ServiceAccount:

```text
incident-collector
```

The associated namespace-scoped Role provides access required for:

```text
Evidence Collection:
    pods
    pods/log
    events

Restart / Scale:
    deployments

Rollback:
    replicasets
```

Permissions are limited to the operations required by the incident automation workflow.

The Collector does not require unrestricted cluster-wide administrative access.

---

# 27. Incident Response Security Model

The incident response design separates:

```text
Detection
Analysis
Approval
Execution
Verification
Persistence
```

The security boundaries are:

```text
Azure Monitor
      |
      v
Authenticated Webhook
      |
      v
Incident Collector
      |
      v
AI Analysis
      |
      v
Human Approval
      |
      v
Restricted Kubernetes RBAC
      |
      v
Runbook Execution
```

The AI analyser does not receive unrestricted Kubernetes permissions.

The human approval stage is required before remediation.

---

# 28. End-to-End Response Sequence

The complete response sequence can be summarized as:

```text
                INCIDENT RESPONSE

Application failure
        |
        v
Prometheus metric anomaly
        |
        v
Azure Monitor alert
        |
        v
Action Group
        |
        v
Incident Collector
        |
        v
Create incident
        |
        v
Collect Kubernetes evidence
        |
        v
AI-assisted RCA
        |
        v
ApprovalPending
        |
        v
Human approval
        |
        v
Approved runbook
        |
        +-------------------+
        |         |         |
        v         v         v
     Restart    Scale    Rollback
        |         |         |
        +---------+---------+
                  |
                  v
          Kubernetes change
                  |
                  v
          Rollout verification
                  |
                  v
        Application verification
                  |
          +-------+-------+
          |       |       |
          v       v       v
        healthz readyz   demo
          200     200     200
                  |
                  v
         Incident result stored
                  |
                  v
          Azure Blob Storage
```

---

# 29. Operational Principles

The incident response implementation follows these principles.

## Detect Before Acting

Monitoring must detect the problem before the remediation workflow begins.

## Collect Evidence

The AI analyser receives Kubernetes evidence rather than relying only on the alert text.

## Human Approval

AI analysis does not directly trigger remediation.

## Deterministic Runbooks

The approved runbook contains controlled logic and parameter validation.

## Verify the Outcome

A Kubernetes API success response is not enough. Rollout and application health are verified.

## Preserve Incident History

The incident and remediation result are persisted in Azure Blob Storage.

## Least Privilege

The Incident Collector receives only the Kubernetes permissions required for its implemented functions.

---

# 30. Incident Response APIs

The main Incident Collector APIs are:

| Method | Endpoint                             | Purpose                      |
| ------ | ------------------------------------ | ---------------------------- |
| POST   | `/alerts`                            | Receive and process alerts   |
| GET    | `/incidents/{incident_id}`           | Retrieve an incident         |
| POST   | `/incidents/{incident_id}/approve`   | Approve a runbook            |
| POST   | `/incidents/{incident_id}/remediate` | Execute the approved runbook |
| GET    | `/runbooks`                          | List registered runbooks     |

---

# 31. Final Incident Response Model

The completed platform follows:

```text
Detect
  ↓
Collect
  ↓
Analyse
  ↓
Approve
  ↓
Remediate
  ↓
Verify
  ↓
Record
```

The architecture intentionally combines AI-assisted analysis with deterministic, approval-gated Kubernetes automation.

The final remediation capabilities are:

```text
restart-sre-api
scale-sre-api
rollback-sre-api
```

Each remediation path includes validation and post-remediation verification.

This provides a controlled incident response workflow from the initial monitoring signal through application recovery and persistent incident recording.

```
```
