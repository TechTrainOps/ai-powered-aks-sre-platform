````markdown
# Testing and Validation

## 1. Overview

This document describes the testing performed for the **AI-Powered AKS SRE & Incident Automation Platform**.

Testing focused on validating the complete application, deployment, monitoring, incident analysis, approval, remediation, and recovery workflow.

The project was validated using both:

- Component-level testing
- Controlled end-to-end incident scenarios

The primary objective was to verify that the platform can detect a controlled application failure, collect evidence, generate AI-assisted RCA, require human approval, execute a remediation runbook, and verify application recovery.

---

# 2. Testing Scope

The following areas were validated:

```text
Application
CI/CD
Terraform
Helm
AKS
ACR
Prometheus
Grafana
Azure Monitor
Incident Collector
AI Analyser
Human Approval
Incident Persistence
Restart Runbook
Scale Runbook
Rollback Runbook
HPA
Post-remediation Verification
Helm / Kubernetes Field Ownership
````

---

# 3. Test Environment

The application was deployed to:

```text
Azure Kubernetes Service (AKS)
Namespace: sre
```

The primary workloads are:

```text
sre-api
incident-collector
ai-analyser
```

The platform uses:

```text
Azure Container Registry
Azure Managed Prometheus
Azure Managed Grafana
Azure Monitor
Azure OpenAI
Azure Blob Storage
```

---

# 4. Application Tests

The `sre-api` application was tested independently before deployment.

The application test suite uses:

```text
pytest
```

The final local application test result was:

```text
3/3 tests passed
```

This validated the basic FastAPI application behavior before deploying the workload to AKS.

---

# 5. Application Endpoint Validation

The deployed `sre-api` application exposes:

```text
/healthz
/readyz
/demo
/metrics
```

The endpoints were validated from inside the Kubernetes pod.

## Health Check

Expected:

```text
HTTP 200
{
  "status": "healthy"
}
```

## Readiness Check

Expected during normal operation:

```text
HTTP 200
{
  "status": "ready"
}
```

## Demo Endpoint

Expected during normal operation:

```text
HTTP 200
{
  "message": "request succeeded"
}
```

## Metrics Endpoint

Expected:

```text
HTTP 200
```

---

# 6. Terraform Validation

Terraform configuration was validated using:

```powershell
terraform validate
```

The validation completed successfully.

Terraform planning was also validated.

A successful plan was observed with:

```text
Plan: 18 to add, 0 to change, 0 to destroy.
```

The required Azure resource providers were subsequently registered and Terraform infrastructure was successfully deployed.

---

# 7. Terraform Deployment Validation

After Terraform deployment, the Azure resources required by the project were successfully provisioned.

The deployed platform included:

```text
Resource Group
Virtual Network
AKS
Azure Container Registry
Log Analytics Workspace
Azure Monitor Workspace
Azure Managed Grafana
Azure OpenAI
User Assigned Managed Identities
Storage
Private Endpoint resources
```

Terraform apply completed successfully.

---

# 8. Azure OpenAI Validation

The Azure OpenAI deployment used by the project was validated with:

```text
Model: gpt-5.4-mini
Version: 2026-03-17
SKU: GlobalStandard
Capacity: 4000
Version Upgrade Option: NoAutoUpgrade
```

The Terraform configuration was also validated to prevent unwanted capacity drift.

---

# 9. Container Image Validation

Three application images were built and deployed:

```text
sre-api
incident-collector
ai-analyser
```

Images were pushed to Azure Container Registry using Azure DevOps build IDs.

A validated build example was:

```text
sre-api:715
incident-collector:715
ai-analyser:715
```

The final deployment confirmed that all three workloads were running the expected `715` images.

---

# 10. Helm Validation

The Kubernetes application was packaged using Helm.

Helm validation included:

```powershell
helm lint .\charts\sre-api
```

and template rendering:

```powershell
helm template sre-api .\charts\sre-api --namespace sre
```

The Helm chart was successfully deployed to AKS.

---

# 11. AKS Deployment Validation

The final deployment state was validated using:

```powershell
kubectl get deployments -n sre
```

The validated state was:

```text
NAME                 IMAGE                                              READY   DESIRED
ai-analyser          acrakssreqtyn6.azurecr.io/ai-analyser:715          2       2
incident-collector   acrakssreqtyn6.azurecr.io/incident-collector:715   1       1
sre-api              acrakssreqtyn6.azurecr.io/sre-api:715              2       2
```

This confirmed:

```text
ai-analyser          2/2
incident-collector   1/1
sre-api              2/2
```

---

# 12. HPA Validation

The `sre-api` Horizontal Pod Autoscaler was validated.

Final configuration:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

A validated state was:

```text
NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS
sre-api   Deployment/sre-api   cpu: 1%/70%   2         8         2
```

This confirmed that the HPA was active and operating within the expected replica range.

---

# 13. Prometheus Metrics Validation

The application metrics endpoint was validated successfully.

The application exposes:

```text
http_requests_total
http_request_duration_seconds
```

The metrics were successfully collected through Azure Managed Prometheus.

The `sre-api` PodMonitor was also validated.

The Managed Prometheus `up` query for the application returned the expected healthy targets.

---

# 14. Grafana Validation

Azure Managed Grafana was successfully connected to the monitoring environment.

The SRE API dashboard was validated with multiple panels covering application and workload telemetry.

The dashboard successfully displayed information including:

```text
HTTP request volume
HTTP error rate
Request latency
Pod availability
Resource utilization
Application metrics
```

---

# 15. Alert Validation

The primary alert tested by the project is:

```text
SREApiHighErrorRate
```

The alert expression is based on the application HTTP 5xx error rate:

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
Threshold: > 5%
Duration: 5 minutes
Severity: Sev2
```

The alert was successfully triggered during controlled failure testing.

---

# 16. Alert Notification Validation

The Azure Monitor Action Group was validated with:

```text
Email notification
Webhook notification
```

The alert successfully generated the configured email notification.

The webhook successfully delivered the alert to the Incident Collector.

---

# 17. Incident Collector Validation

The Incident Collector was validated for:

```text
Alert ingestion
Incident creation
Kubernetes evidence collection
AI analyser integration
Approval handling
Remediation execution
Incident persistence
```

The service successfully handled the complete incident workflow.

---

# 18. Kubernetes Evidence Collection Validation

The Incident Collector successfully collected Kubernetes evidence during the controlled incident.

The evidence included:

```text
Pod state
Pod readiness
Restart count
Container state
Container image
Deployment state
Replica information
Pod logs
Kubernetes events
```

During the readiness failure scenario, the evidence showed:

```text
Pods:
Running but NotReady

Restart count:
0

/healthz:
HTTP 200

/readyz:
HTTP 503

Kubernetes events:
Readiness probe failures
```

This confirmed that the Collector was able to capture the application and Kubernetes state surrounding the incident.

---

# 19. AI Analysis Validation

The Incident Collector successfully sent the collected incident context to the AI Analyser.

The AI Analyser returned structured information including:

```text
Incident ID
Summary
Root Cause
Confidence
Severity
Evidence
Recommended Action
```

A controlled readiness incident produced an AI analysis with:

```text
Evaluated 5xx rate: approximately 44%
Severity: Sev2
Confidence: 0.78
```

The analysis identified the readiness failure and repeated HTTP 503 responses as the primary evidence.

---

# 20. Human Approval Validation

The approval workflow was successfully validated.

The incident initially entered:

```text
ApprovalPending
```

An approved runbook request was then submitted.

Example:

```json
{
  "runbook": "restart-sre-api",
  "parameters": {},
  "approved_by": "shakir"
}
```

The approval API returned:

```text
status = 200
approval.status = Approved
```

This validated that remediation could not proceed until the incident contained an approved runbook.

---

# 21. Incident Persistence Validation

Incident records were persisted to Azure Blob Storage.

The storage layout is:

```text
incidents/
    <incident-id>.json
```

The incident record stores:

```text
Alert
Evidence
AI Analysis
Approval
Remediation
```

Incident retrieval through:

```text
GET /incidents/{incident_id}
```

was successfully validated.

---

# 22. Restart Runbook Test

## Objective

Validate that the platform can detect a controlled readiness failure, obtain approval, restart the `sre-api` Deployment, and verify application recovery.

## Test Method

The application failure mode was enabled on both `sre-api` pods.

The operation returned:

```text
200
{"failure_mode":true}
```

Both pods subsequently became:

```text
0/1 Running
```

The readiness endpoint returned:

```text
HTTP 503
```

while the application process remained running.

---

# 23. Restart Incident Detection

The controlled failure generated the:

```text
SREApiHighErrorRate
```

alert.

The evaluated 5xx error rate was:

```text
44.252%
```

The Incident Collector received the alert and created incident:

```text
0c19911e-9124-424a-9cbc-1fcaedb3b7f6
```

The AI analysis identified:

```text
Pods Running but NotReady
Repeated readiness probe failures
/readyz returning HTTP 503
/healthz remaining HTTP 200
No pod restart loop
```

---

# 24. Restart Approval

The incident was approved for:

```text
restart-sre-api
```

with:

```json
{
  "runbook": "restart-sre-api",
  "parameters": {},
  "approved_by": "shakir"
}
```

The approval operation returned HTTP 200.

---

# 25. Restart Remediation Result

The restart runbook executed successfully.

The remediation result reported:

```text
success = true
```

Rollout verification:

```text
desired_replicas   = 2
updated_replicas   = 2
available_replicas = 2
unavailable_replicas = 0
```

The Deployment was restarted using the remediation timestamp annotation.

Restart time:

```text
2026-09-20T17:22:07.364145+00:00
```

The Deployment revision changed from:

```text
34
```

to:

```text
35
```

---

# 26. Restart Health Verification

After remediation, the runbook verified:

```text
healthz = 200
readyz  = 200
demo    = 200
```

The final pod state was:

```text
sre-api pods:
2/2 Running
```

The restart remediation was therefore marked:

```text
Succeeded
```

This validated the complete incident-to-recovery workflow.

---

# 27. Scale Runbook Test

## Objective

Validate that the scale runbook can safely change the replica count, verify Kubernetes reconciliation, verify replica availability, and validate application health.

## Test Scenario

Initial state:

```text
replicas = 2
```

Requested state:

```text
replicas = 3
```

The runbook successfully changed the Deployment.

Observed state:

```text
requested replicas = 3
observed replicas = 3
available replicas = 3
unavailable replicas = 0
```

Application verification returned:

```text
healthz = 200
readyz  = 200
demo    = 200
```

---

# 28. Scale Reconciliation Validation

The scale runbook specifically validates the requested replica count before checking application health.

The implementation uses:

```text
Replica reconciliation timeout: 30 seconds
Polling interval: 3 seconds
```

After the requested count is reached, availability is checked for up to:

```text
120 seconds
```

with:

```text
3 second polling interval
```

This behavior was tested successfully.

The runbook was also validated against a replica-count mismatch scenario and correctly returned:

```text
ReplicaCountMismatch
```

instead of reporting false success.

---

# 29. HPA Restoration After Scale Test

The scale test temporarily changed the application replica count.

After the remediation test, the HPA configuration was restored to:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

The final HPA state returned to:

```text
2 replicas
```

and normal CPU utilization was observed.

---

# 30. Rollback Runbook Test

## Objective

Validate that the rollback runbook can identify the immediately previous Deployment revision, restore its pod template, verify the target image, complete the rollout, and verify application recovery.

## Test Scenario

Initial application image:

```text
acrakssreqtyn6.azurecr.io/sre-api:713
```

Current Deployment revision:

```text
32
```

The previous Deployment revision was:

```text
31
```

The previous image was:

```text
acrakssreqtyn6.azurecr.io/sre-api:712
```

---

# 31. Rollback Incident Flow

The rollback test followed:

```text
Controlled failure
      |
      v
Alert
      |
      v
Incident creation
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
Previous image restored
      |
      v
Rollout verification
      |
      v
Application verification
```

---

# 32. Rollback Result

The rollback remediation completed successfully.

The result included:

```text
current_revision = 32
target_revision  = 31

current_image:
acrakssreqtyn6.azurecr.io/sre-api:713

target_image:
acrakssreqtyn6.azurecr.io/sre-api:712

final_revision = 33

final_image:
acrakssreqtyn6.azurecr.io/sre-api:712
```

Rollout result:

```text
desired_replicas   = 2
updated_replicas   = 2
available_replicas = 2
unavailable_replicas = 0
```

Application verification:

```text
healthz = 200
readyz  = 200
demo    = 200
```

The rollback remediation was therefore marked:

```text
Succeeded
```

---

# 33. Helm Field Ownership Test

During rollback testing, the remediation operation changed the `sre-api` image field.

Kubernetes Server-Side Apply field ownership recorded the image field under the remediation field manager:

```text
OpenAPI-Generator
```

The next normal Helm deployment initially failed with:

```text
conflict with "OpenAPI-Generator"

.spec.template.spec.containers[name="sre-api"].image
```

The Helm deployment was updated to use:

```text
--force-conflicts
```

---

# 34. Helm Recovery Validation

After adding:

```text
--force-conflicts
```

the Azure DevOps pipeline successfully deployed a newer image.

Validated final image:

```text
acrakssreqtyn6.azurecr.io/sre-api:715
```

Final Deployment:

```text
Revision: 34
Ready:    2
Desired:  2
```

The image field ownership was then verified through Kubernetes managed fields.

The result showed:

```text
helm
```

owning the:

```text
.spec.template.spec.containers[name="sre-api"].image
```

field.

This validated that normal Helm deployment can reclaim the field after remediation.

---

# 35. Final Deployment State Validation

After the final pipeline deployment, the three workloads were:

```text
ai-analyser          acrakssreqtyn6.azurecr.io/ai-analyser:715          2/2
incident-collector   acrakssreqtyn6.azurecr.io/incident-collector:715   1/1
sre-api              acrakssreqtyn6.azurecr.io/sre-api:715              2/2
```

The HPA was:

```text
sre-api
2 replicas
min 2
max 8
CPU target 70%
```

Application endpoints returned:

```text
healthz = 200
readyz  = 200
demo    = 200
```

---

# 36. End-to-End Incident Validation

The final restart test validated the complete operational workflow:

```text
Application failure
        |
        v
Readiness failure
        |
        v
Prometheus metrics
        |
        v
Azure Monitor alert
        |
        v
Incident Collector
        |
        v
Kubernetes evidence
        |
        v
AI-assisted RCA
        |
        v
Human approval
        |
        v
Restart runbook
        |
        v
Kubernetes rollout
        |
        v
Health verification
        |
        v
Incident marked Succeeded
        |
        v
Incident persisted
```

The final remediation successfully recovered the application.

---

# 37. Test Results Summary

| Test Area                      | Result   |
| ------------------------------ | -------- |
| Application unit tests         | ✅ Passed |
| Terraform validate             | ✅ Passed |
| Terraform plan                 | ✅ Passed |
| Terraform apply                | ✅ Passed |
| Azure provider registration    | ✅ Passed |
| Container image build          | ✅ Passed |
| ACR image push                 | ✅ Passed |
| Helm lint                      | ✅ Passed |
| Helm deployment                | ✅ Passed |
| AKS rollout                    | ✅ Passed |
| Application health             | ✅ Passed |
| Application readiness          | ✅ Passed |
| Application demo endpoint      | ✅ Passed |
| Prometheus metrics             | ✅ Passed |
| Managed Prometheus             | ✅ Passed |
| Grafana dashboard              | ✅ Passed |
| Azure Monitor alert            | ✅ Passed |
| Email notification             | ✅ Passed |
| Incident webhook               | ✅ Passed |
| Kubernetes evidence collection | ✅ Passed |
| AI analysis                    | ✅ Passed |
| Human approval                 | ✅ Passed |
| Incident persistence           | ✅ Passed |
| Restart runbook                | ✅ Passed |
| Scale runbook                  | ✅ Passed |
| Rollback runbook               | ✅ Passed |
| HPA validation                 | ✅ Passed |
| Helm field ownership recovery  | ✅ Passed |
| Post-remediation verification  | ✅ Passed |

---

# 38. Final Test Matrix

| Scenario              | Initial State          | Action              | Expected Result            | Result |
| --------------------- | ---------------------- | ------------------- | -------------------------- | ------ |
| Application health    | Healthy                | Call `/healthz`     | HTTP 200                   | ✅      |
| Application readiness | Ready                  | Call `/readyz`      | HTTP 200                   | ✅      |
| Application traffic   | Healthy                | Call `/demo`        | HTTP 200                   | ✅      |
| Metrics               | Application running    | Call `/metrics`     | Metrics available          | ✅      |
| Readiness failure     | Running / Ready        | Enable failure mode | Pods become NotReady       | ✅      |
| Alerting              | Elevated 5xx           | Wait for alert rule | Alert fires                | ✅      |
| Incident creation     | Alert received         | Process webhook     | Incident created           | ✅      |
| Evidence collection   | Incident created       | Query AKS           | Evidence collected         | ✅      |
| AI RCA                | Evidence available     | Analyse incident    | Structured RCA             | ✅      |
| Approval              | Pending                | Approve runbook     | Approved                   | ✅      |
| Restart               | Pods NotReady          | Run restart         | Rollout + health pass      | ✅      |
| Scale                 | 2 replicas             | Request 3 replicas  | 3 available                | ✅      |
| Rollback              | Revision 32            | Roll back           | Previous revision restored | ✅      |
| Helm recovery         | Remediation owns image | CI/CD deployment    | Helm reclaims image        | ✅      |

---

# 39. Final Validation Outcome

The platform successfully demonstrated:

```text
Detect
  ✅

Collect
  ✅

Analyse
  ✅

Approve
  ✅

Remediate
  ✅

Verify
  ✅

Record
  ✅
```

The three implemented remediation paths were validated:

```text
restart-sre-api   ✅
scale-sre-api     ✅
rollback-sre-api  ✅
```

The final end-to-end test confirmed that a controlled application failure can move through monitoring, incident creation, Kubernetes evidence collection, AI-assisted RCA, human approval, remediation, and application recovery.

---

# 40. Testing Conclusion

The functional testing required for the current project scope is complete.

The platform has been validated across the complete incident automation lifecycle:

```text
Monitoring
     ↓
Alerting
     ↓
Incident Collection
     ↓
AI-assisted RCA
     ↓
Human Approval
     ↓
Automated Remediation
     ↓
Application Verification
     ↓
Incident Persistence
```

The testing confirms that the platform can perform controlled Kubernetes remediation through:

```text
Restart
Scale
Rollback
```

while maintaining a human approval boundary and verifying the outcome of each remediation action.

```
```
