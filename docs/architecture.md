````markdown
# Architecture

## 1. Architecture Overview

The **AI-Powered AKS SRE & Incident Automation Platform** is designed as an event-driven incident response system running on Azure.

The platform combines infrastructure as code, CI/CD, Kubernetes, observability, AI-assisted analysis, human approval, and controlled remediation into a single workflow.

At a high level:

```text
                              +----------------------+
                              |      Developer       |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |     Git Repository   |
                              |        GitHub        |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |  Azure DevOps        |
                              |  CI/CD Pipeline      |
                              +----------+-----------+
                                         |
                    +--------------------+--------------------+
                    |                    |                    |
                    v                    v                    v
              Terraform            Application          Helm
              Validation             Tests             Validation
                    |                    |                    |
                    +--------------------+--------------------+
                                         |
                                         v
                              +----------------------+
                              | Container Build      |
                              | & Security Scan      |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              | Azure Container      |
                              | Registry (ACR)       |
                              +----------+-----------+
                                         |
                                         v
                  +------------------------------------------------+
                  |                     AKS                        |
                  |                                                |
                  |  Namespace: sre                                |
                  |                                                |
                  |  +----------------+                            |
                  |  |    sre-api     |                            |
                  |  |    FastAPI     |                            |
                  |  |                |                            |
                  |  | /healthz       |                            |
                  |  | /readyz        |                            |
                  |  | /metrics       |                            |
                  |  | /demo          |                            |
                  |  +-------+--------+                            |
                  |          |                                     |
                  |          |                                     |
                  |          |              +-------------------+  |
                  |          |              | Incident Collector|  |
                  |          |              |     FastAPI       |  |
                  |          |              +---------+---------+  |
                  |          |                        |            |
                  |          |                        v            |
                  |          |              +-------------------+  |
                  |          |              |   AI Analyser     |  |
                  |          |              |     FastAPI       |  |
                  |          |              +-------------------+  |
                  |          |                                     |
                  +----------|-------------------------------------+
                             |
                             | /metrics
                             v
                  +--------------------------+
                  | Azure Managed Prometheus |
                  +------------+-------------+
                               |
                    +----------+----------+
                    |                     |
                    v                     v
          +-------------------+   +----------------------+
          | Azure Managed     |   | Azure Monitor        |
          | Grafana           |   | Prometheus Alert     |
          +-------------------+   +----------+-----------+
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
                      +----------------------+----------------------+
                      |                      |                      |
                      v                      v                      v
               Kubernetes API          Pod Logs             Kubernetes Events
                      |                      |                      |
                      +----------------------+----------------------+
                                             |
                                             v
                                  +----------------------+
                                  | Structured Incident  |
                                  | Evidence             |
                                  +----------+-----------+
                                             |
                                             v
                                  +----------------------+
                                  | AI Analyser          |
                                  | Azure OpenAI         |
                                  +----------+-----------+
                                             |
                                             v
                                  +----------------------+
                                  | Human Approval       |
                                  +----------+-----------+
                                             |
                                             v
                                  +----------------------+
                                  | Approved Runbook     |
                                  +----------+-----------+
                                             |
                       +---------------------+---------------------+
                       |                     |                     |
                       v                     v                     v
                  Restart Runbook       Scale Runbook       Rollback Runbook
                       |                     |                     |
                       +---------------------+---------------------+
                                             |
                                             v
                                  +----------------------+
                                  | Kubernetes           |
                                  | Remediation          |
                                  +----------+-----------+
                                             |
                                             v
                                  +----------------------+
                                  | Rollout & Health     |
                                  | Verification         |
                                  +----------+-----------+
                                             |
                                             v
                                  +----------------------+
                                  | Azure Blob Storage   |
                                  | Incident JSON Record |
                                  +----------------------+
````

---

# 2. Major Architectural Components

## 2.1 Source Repository

The project source code contains:

* FastAPI application
* AI analyser
* Incident Collector
* Kubernetes Helm chart
* Terraform infrastructure
* Tests
* Azure DevOps pipeline definition
* Remediation runbooks

The repository acts as the single source of truth for application and deployment configuration.

---

# 3. Infrastructure Layer

Azure infrastructure is provisioned using **Terraform**.

The infrastructure layer provides the platform required by the application and incident automation components.

The main Azure resources include:

```text
Azure Resource Group
        |
        +-- Virtual Network
        |
        +-- Azure Kubernetes Service
        |
        +-- Azure Container Registry
        |
        +-- Log Analytics Workspace
        |
        +-- Azure Monitor Workspace
        |
        +-- Azure Managed Grafana
        |
        +-- Azure OpenAI
        |
        +-- User Assigned Managed Identities
        |
        +-- Azure Storage Account
        |
        +-- Private Endpoint resources
```

Terraform state is stored remotely in Azure Storage using Azure AD / workload identity authentication.

The Terraform backend is separated from other project storage and is not dependent on an existing storage account belonging to another project.

---

# 4. CI/CD Architecture

Azure DevOps provides the CI/CD layer.

The pipeline is responsible for validating, building, scanning, publishing, and deploying the application.

```text
Source Commit
     |
     v
Terraform Validate
     |
     v
Application Tests
     |
     v
Helm Validation
     |
     v
Container Build
     |
     v
Security Scan
     |
     v
Push Images to ACR
     |
     v
Helm Deployment
     |
     v
AKS Rollout Validation
```

Three application images are deployed:

```text
sre-api
incident-collector
ai-analyser
```

Images are tagged using the Azure DevOps build ID.

Example:

```text
acrakssreqtyn6.azurecr.io/sre-api:<build-id>
acrakssreqtyn6.azurecr.io/incident-collector:<build-id>
acrakssreqtyn6.azurecr.io/ai-analyser:<build-id>
```

---

# 5. AKS Architecture

The application workloads run inside an AKS cluster in the `sre` namespace.

The namespace contains the following primary workloads:

```text
sre
|
+-- sre-api
|
+-- incident-collector
|
+-- ai-analyser
|
+-- Supporting Kubernetes resources
    |
    +-- Services
    +-- ServiceAccounts
    +-- Role
    +-- RoleBinding
    +-- HPA
    +-- PDB
    +-- PodMonitor
```

---

# 6. sre-api

The `sre-api` component is the application being monitored and remediated.

It is implemented using Python and FastAPI.

The application exposes:

```text
GET  /healthz
GET  /readyz
GET  /metrics
GET  /demo
POST /admin/failure-mode
```

## Health

`/healthz` verifies that the application process is functioning.

```text
GET /healthz
        |
        v
HTTP 200
{
  "status": "healthy"
}
```

## Readiness

`/readyz` determines whether the pod is ready to receive traffic.

```text
GET /readyz
        |
        +---- Normal --> HTTP 200
        |
        +---- Failure Mode --> HTTP 503
```

## Demonstration Endpoint

`/demo` represents normal application traffic.

```text
GET /demo
        |
        +---- Normal --> HTTP 200
        |
        +---- Failure Mode --> HTTP 500
```

## Metrics

`/metrics` exposes Prometheus metrics including:

```text
http_requests_total
http_request_duration_seconds
```

These metrics form the basis for application-level monitoring and alerting.

---

# 7. Controlled Failure Injection

The application contains a controlled failure mechanism through:

```text
POST /admin/failure-mode
```

This is used only for testing the incident automation workflow.

When enabled:

```text
/readyz -> 503
/demo   -> 500
```

The pods remain running and do not crash.

This creates a controlled readiness and application failure that can be detected by monitoring.

The mechanism allows repeatable incident testing without introducing an actual software defect into the application.

---

# 8. Kubernetes Availability Architecture

The `sre-api` deployment is configured with:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

The Horizontal Pod Autoscaler monitors CPU utilization and can adjust the number of replicas between the configured minimum and maximum.

The application also uses:

```text
Liveness Probe
Readiness Probe
Horizontal Pod Autoscaler
Pod Disruption Budget
```

The readiness probe is especially important for the incident automation scenario because an application can remain alive while becoming unavailable to users.

---

# 9. Incident Collector

The Incident Collector is the central orchestration component for incident handling.

It is implemented using FastAPI.

Its responsibilities include:

```text
Receive alert
     |
     v
Authenticate alert
     |
     v
Create incident
     |
     v
Collect Kubernetes evidence
     |
     v
Call AI Analyser
     |
     v
Persist incident
     |
     v
Wait for approval
     |
     v
Execute approved runbook
     |
     v
Verify remediation
     |
     v
Update incident result
```

Main APIs:

```text
POST /alerts
GET  /incidents/{incident_id}
POST /incidents/{incident_id}/approve
POST /incidents/{incident_id}/remediate
GET  /runbooks
```

---

# 10. Alert Ingestion Architecture

The monitoring path starts with application metrics.

```text
sre-api
   |
   | /metrics
   v
Azure Managed Prometheus
   |
   v
Azure Monitor Prometheus Alert
   |
   v
Action Group
   |
   +------------------> Email Notification
   |
   +------------------> Incident Collector Webhook
```

The example alert used by this project detects a sustained HTTP 5xx error rate.

The alert is configured with:

```text
Threshold: > 5%
Duration:  5 minutes
Severity:  Sev2
```

The alert therefore does not trigger simply because of a single failed request.

---

# 11. Monitoring Architecture

## Metrics Collection

```text
FastAPI Application
       |
       v
Prometheus Metrics
       |
       v
Azure Managed Prometheus
```

## Visualization

```text
Azure Managed Prometheus
       |
       v
Azure Managed Grafana
```

Grafana provides operational visibility into application and Kubernetes metrics.

The dashboard covers operational information such as:

```text
Request volume
HTTP error rate
Request latency
Application metrics
Pod availability
Resource utilization
Workload health
```

## Alerting

```text
Azure Managed Prometheus
       |
       v
Azure Monitor
       |
       v
Prometheus Alert Rule
       |
       v
Action Group
```

---

# 12. Kubernetes Evidence Collection

When an alert reaches the Incident Collector, it gathers evidence directly from the Kubernetes API.

The evidence collection path is:

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

The Collector uses the Kubernetes Python client.

Evidence includes information such as:

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

This evidence is passed into the AI analysis process.

---

# 13. AI Analysis Architecture

The AI Analyser receives structured incident information from the Incident Collector.

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

The analyser generates information such as:

```text
Incident Summary
Probable Root Cause
Confidence
Severity
Evidence
Recommended Action
```

Example structure:

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

The AI layer is intentionally separated from the execution layer.

---

# 14. Human Approval Architecture

The AI analyser does not have direct permission to execute remediation.

Instead:

```text
AI Analysis
    |
    v
Recommended Action
    |
    v
Human Approval
    |
    v
Approved Runbook
    |
    v
Remediation
```

This creates a human-controlled boundary between AI analysis and infrastructure changes.

An approval request contains:

```json
{
  "runbook": "restart-sre-api",
  "parameters": {},
  "approved_by": "operator"
}
```

The Collector stores the approval state as part of the incident record.

---

# 15. Remediation Architecture

The approved remediation request is handled by the Incident Collector.

```text
Approved Incident
       |
       v
Runbook Registry
       |
       +----------------------+
       |          |           |
       v          v           v
    Restart     Scale      Rollback
       |          |           |
       +----------+-----------+
                  |
                  v
             Kubernetes API
                  |
                  v
          Rollout / Verification
```

The runbooks inherit from a common runbook abstraction.

The common interface provides:

```text
Parameter validation
Execution
Deployment context
Kubernetes clients
Rollout waiting
Health verification
```

---

# 16. Restart Architecture

The restart runbook performs a controlled Kubernetes Deployment restart.

```text
restart-sre-api
       |
       v
Read sre-api Deployment
       |
       v
Update pod-template annotation
       |
       v
Kubernetes detects template change
       |
       v
New ReplicaSet
       |
       v
New Pods
       |
       v
Rollout Verification
       |
       v
Application Health Verification
```

The runbook uses the annotation:

```text
sre.azure.com/remediation-restarted-at
```

The annotation changes the Deployment pod template and causes Kubernetes to create a new ReplicaSet.

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

# 17. Scale Architecture

The scale runbook changes the replica count of the `sre-api` Deployment.

```text
scale-sre-api
       |
       v
Validate requested replicas
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

The remediation range is restricted to:

```text
1 <= replicas <= 5
```

The implementation explicitly checks that Kubernetes has reconciled the requested replica count before continuing.

This prevents the runbook from reporting success simply because the patch request was accepted by the API.

---

# 18. Rollback Architecture

The rollback runbook restores the immediately previous Deployment revision.

```text
rollback-sre-api
       |
       v
Read current Deployment
       |
       v
Read current revision
       |
       v
List sre-api ReplicaSets
       |
       v
Find previous Deployment revision
       |
       v
Read previous Pod template
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

The runbook derives the rollback target from Kubernetes Deployment history rather than accepting an arbitrary image from the approval request.

This ensures that rollback is tied to the known previous Deployment revision.

---

# 19. Helm and Kubernetes Field Ownership

Helm is the normal Deployment manager for the application.

The remediation layer can also update certain Deployment fields.

Because Kubernetes Server-Side Apply tracks field ownership, a remediation operation can temporarily become the owner of a field normally managed by Helm.

During rollback testing, the `sre-api` container image field became associated with the `OpenAPI-Generator` field manager.

The next Helm deployment initially encountered:

```text
conflict with "OpenAPI-Generator"

.spec.template.spec.containers[name="sre-api"].image
```

The Helm deployment was therefore configured to use:

```text
--force-conflicts
```

The resulting behavior is:

```text
                     Normal Deployment
                            |
                            v
                          Helm
                            |
                            v
                    sre-api image
                            |
                            v
                    Normal operation

                            |
                      Incident occurs
                            |
                            v
                       Rollback
                            |
                            v
                   Remediation API
                            |
                            v
                   Previous image
                            |
                            v
                  Application recovery

                            |
                      Next CI/CD run
                            |
                            v
                   Helm --force-conflicts
                            |
                            v
                  Helm owns image field
                            |
                            v
                    New image deployed
```

This allows controlled remediation and regular CI/CD deployment to coexist.

---

# 20. Incident Storage Architecture

The Incident Collector persists incident information in Azure Blob Storage.

```text
Incident Collector
       |
       v
Azure Blob Storage
       |
       v
incidents/
    |
    +-- <incident-id>.json
```

The incident document contains information such as:

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

This provides persistent incident history and allows the incident state to be retrieved independently of the Kubernetes workload lifecycle.

---

# 21. Incident State Model

The incident state is represented through separate analysis, approval, and remediation information.

A typical successful incident follows:

```text
Alert Received
      |
      v
Incident Created
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
Succeeded
      |
      v
Verified Recovery
```

Failure states can include:

```text
AnalysisFailed
RemediationFailed
VerificationFailed
```

This separates the incident lifecycle from the individual Kubernetes operation.

---

# 22. Kubernetes RBAC Architecture

The Incident Collector uses a dedicated ServiceAccount:

```text
incident-collector
```

The ServiceAccount is bound to a namespace-scoped Role.

The Role provides permissions required by the automation:

```text
Core API
---------
pods
pods/log
events

get
list
watch


Apps API
--------
deployments
    get
    patch

replicasets
    get
    list
```

The ReplicaSet permissions are required specifically by the rollback runbook to identify the previous Deployment revision.

The architecture intentionally avoids granting unrestricted cluster-wide access to the Incident Collector.

---

# 23. Azure Identity Architecture

Azure resource access uses identity-based authentication.

The architecture separates application responsibilities using dedicated identities where required.

Conceptually:

```text
Incident Collector Identity
       |
       +---- Azure Blob Storage

AI Analyser / Application Identity
       |
       +---- Azure OpenAI
```

The Incident Collector uses Azure identity authentication through `DefaultAzureCredential`.

The architecture avoids embedding long-lived Azure credentials directly in application source code.

---

# 24. Container Architecture

The application components are containerized independently.

```text
Azure Container Registry
|
+-- sre-api
|
+-- incident-collector
|
+-- ai-analyser
```

The containers use Python 3.11.

The `sre-api` image is designed with a non-root execution model and read-only filesystem configuration where supported by the workload.

The Incident Collector container also runs as a non-root user.

This provides isolation between application components and reduces unnecessary container privileges.

---

# 25. End-to-End Operational Flow

The complete operational architecture can be summarized as:

```text
                         NORMAL OPERATION
                               |
                               v
                       FastAPI Application
                               |
                               v
                         Prometheus Metrics
                               |
                +--------------+--------------+
                |                             |
                v                             v
             Grafana                    Azure Monitor
                                             |
                                             v
                                         Alert Rule
                                             |
                                             v
                                       Action Group
                                             |
                                             v
                                  Incident Collector
                                             |
                         +-------------------+-------------------+
                         |                   |                   |
                         v                   v                   v
                       Pods                Logs              K8s Events
                         |                   |                   |
                         +-------------------+-------------------+
                                             |
                                             v
                                         AI Analyser
                                             |
                                             v
                                         Azure OpenAI
                                             |
                                             v
                                      AI-assisted RCA
                                             |
                                             v
                                       Human Approval
                                             |
                                             v
                                      Runbook Registry
                                             |
                            +----------------+----------------+
                            |                |                |
                            v                v                v
                         Restart           Scale           Rollback
                            |                |                |
                            +----------------+----------------+
                                             |
                                             v
                                     Kubernetes API
                                             |
                                             v
                                    Rollout Verification
                                             |
                                             v
                                    Health Verification
                                             |
                                    +--------+--------+
                                    |        |        |
                                    v        v        v
                                  200      200      200
                                healthz   readyz   demo
                                             |
                                             v
                                    Incident JSON Record
                                             |
                                             v
                                      Azure Blob Storage
```

---

# 26. Controlled Incident Flow

A controlled incident follows this sequence:

```text
1. Enable application failure mode
        |
        v
2. /readyz begins returning HTTP 503
        |
        v
3. Pods remain Running but become NotReady
        |
        v
4. /demo returns HTTP 500
        |
        v
5. Prometheus metrics reflect elevated 5xx errors
        |
        v
6. Azure Monitor alert fires
        |
        v
7. Action Group sends webhook
        |
        v
8. Incident Collector creates incident
        |
        v
9. Kubernetes evidence is collected
        |
        v
10. AI Analyser generates RCA
        |
        v
11. Human approves remediation
        |
        v
12. Selected runbook executes
        |
        v
13. Deployment rollout completes
        |
        v
14. Health endpoints are verified
        |
        v
15. Incident state is updated
        |
        v
16. Incident record is persisted
```

---

# 27. Architecture Design Principles

The project follows several design principles.

## Separation of Concerns

Each component has a defined responsibility:

```text
Terraform
    -> Infrastructure

Azure DevOps
    -> CI/CD

Helm
    -> Kubernetes deployment

sre-api
    -> Application workload

Managed Prometheus
    -> Metrics collection

Grafana
    -> Visualization

Azure Monitor
    -> Alerting

Incident Collector
    -> Incident orchestration

AI Analyser
    -> RCA assistance

Runbooks
    -> Controlled remediation

Blob Storage
    -> Incident persistence
```

## Human in the Loop

AI analysis does not directly execute remediation.

```text
AI
 |
 v
Recommendation
 |
 v
Human Approval
 |
 v
Runbook
```

## Least Privilege

The Incident Collector is given only the Kubernetes permissions required for evidence collection and remediation.

## Deterministic Remediation

Runbooks validate inputs and verify the outcome instead of assuming a successful Kubernetes API request means the application has recovered.

## Observable Remediation

Every remediation operation performs rollout and application health verification.

## Infrastructure as Code

Azure platform resources are defined and managed through Terraform.

---

# 28. Final Architecture Summary

The platform provides an end-to-end path from application telemetry to controlled automated remediation:

```text
Detect
  |
  v
Collect
  |
  v
Analyse
  |
  v
Approve
  |
  v
Remediate
  |
  v
Verify
  |
  v
Record
```

The architecture brings together:

```text
Azure
+
Terraform
+
Azure DevOps
+
AKS
+
Helm
+
ACR
+
Prometheus
+
Grafana
+
Azure Monitor
+
Azure OpenAI
+
Kubernetes API
+
RBAC
+
Azure Blob Storage
```

The result is an AI-assisted Kubernetes SRE workflow that can detect a failure, gather operational evidence, produce an AI-assisted RCA, wait for an explicit human decision, perform a controlled remediation, and verify that the application has recovered.

```
```