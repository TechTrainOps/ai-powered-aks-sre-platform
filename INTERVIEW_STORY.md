# Interview Story

## One-minute explanation

I built an AI-assisted SRE platform on AKS that turns a production-style alert into a structured incident investigation. Azure Monitor detects the failure, an incident collector pulls recent logs, Kubernetes events and metric context, and an Azure OpenAI service produces an evidence-backed RCA and runbook suggestion. An engineer reviews and approves the runbook before any remediation is executed.

The point was not just to call an LLM. The project shows the complete engineering path: infrastructure as code, secure identity, Kubernetes operations, CI/CD, observability, incident collection, AI analysis, and human approval.

## What I would discuss technically

### Why Workload Identity

I did not put an Azure OpenAI API key into Kubernetes. AKS OIDC and Microsoft Entra Workload ID let the analyser pod obtain tokens for the user-assigned managed identity. The identity gets the minimum Azure role needed to call Azure OpenAI.

### Why an incident collector

The LLM should not poll Azure and Kubernetes directly. The collector has deterministic access to the evidence sources, normalizes the data, applies a time window and passes a bounded evidence package to the model.

### Why not autonomous remediation

An incident log can contain attacker-controlled text. Executing commands from model output would create an unsafe control loop. The model produces a recommendation, the engineer approves it, and the remediation system can execute only an approved runbook.

### Why HPA plus PDB

The API is stateless, so HPA handles changing request load. Resource requests are explicitly configured because CPU-based HPA uses requested CPU as its utilization baseline. PDB protects availability during voluntary disruptions.

## Example incident walkthrough

1. New image is deployed.
2. API starts returning HTTP 500.
3. 5xx alert fires.
4. Collector receives the alert.
5. Collector queries the last 15 minutes of logs.
6. Collector reads Kubernetes warning events.
7. Collector gathers application metric context.
8. Evidence is sent to Azure OpenAI.
9. Model returns RCA confidence and runbook.
10. Engineer verifies the deployment correlation.
11. Engineer approves the rollback runbook.
12. Rollback is executed by the controlled operator workflow.
13. Readiness, error rate and rollout state are checked.
14. Incident is closed with an audit trail.

## Resume bullets

- Designed and implemented an AI-assisted AKS SRE platform using Terraform, Azure Kubernetes Service, Azure Monitor, managed Prometheus, Azure Managed Grafana and Azure DevOps.
- Implemented Microsoft Entra Workload Identity for secretless pod-to-Azure authentication and RBAC-scoped identities for Azure OpenAI and Log Analytics access.
- Built Python/FastAPI services exposing Prometheus metrics, health probes and controlled failure modes for incident simulations.
- Automated incident evidence collection across Kubernetes events, Log Analytics and Prometheus-compatible metrics, then generated structured RCA and runbook recommendations through Azure OpenAI.
- Added human approval controls so AI output could not directly execute remediation commands.
- Built Azure DevOps CI/CD with Terraform validation, unit tests, Helm linting, container builds, Trivy scanning, ACR publishing, AKS deployment and post-deployment smoke tests.
