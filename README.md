# AI-Powered AKS SRE & Incident Automation Platform

A portfolio-grade Azure platform that detects an AKS incident, collects evidence from Kubernetes, Log Analytics and Prometheus-compatible metrics, asks Azure OpenAI for a structured RCA, presents a human-approval gate, and produces a runbook suggestion without executing remediation automatically.

## Architecture

Developer -> Azure Repos/GitHub -> Azure DevOps Pipeline -> Terraform validation -> tests -> Helm validation -> container build -> Trivy scan -> ACR -> AKS -> observability -> Azure Monitor alert -> Incident Collector -> AI Incident Analyser -> human approval -> approved runbook.

## Important implementation choices

- AKS uses Microsoft Entra Workload ID and OIDC for pod-to-Azure authentication.
- The incident collector and analyser use `DefaultAzureCredential` so local development can use Azure CLI credentials and AKS can use Workload Identity.
- Azure OpenAI is called through the current Responses API.
- The AI output is constrained to a structured incident record.
- No command is executed by the AI service. Approval only changes incident state and stores the proposed runbook.
- Managed Prometheus scrapes `/metrics` from the API using scrape annotations. The collector supports a Prometheus-compatible query endpoint through `PROMETHEUS_QUERY_URL` when available; otherwise it falls back to the app's `/metrics` endpoint for a lab.

## Repository layout

```text
.
├── .azuredevops/azure-pipelines.yml
├── app/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/test_main.py
├── ai-analyser/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/test_main.py
├── incident-collector/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/test_main.py
├── charts/sre-api/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/*.yaml
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   └── terraform.tfvars.example
└── scripts/
    ├── bootstrap.sh
    ├── configure-monitoring.sh
    ├── deploy.sh
    ├── smoke-test.sh
    └── create-openai-deployment.sh
```

## 0. Prerequisites

Use a Linux shell, WSL, Git Bash or Cloud Shell.

Install:

- Azure CLI
- kubectl
- Helm 3
- Terraform 1.8+ or newer
- Docker
- Git
- Python 3.11+

Login and select your subscription:

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
az account show --output table
```

## 1. Clone or create the repo

```bash
git init
cp -r . /path/to/your/repo
cd /path/to/your/repo
```

Create a branch:

```bash
git checkout -b feature/ai-aks-sre
```

## 2. Provision Azure infrastructure

The Terraform stack creates:

- Resource group
- VNet and AKS subnet
- ACR
- AKS Standard cluster
- Log Analytics workspace
- Azure Monitor workspace
- Azure Managed Grafana
- Azure OpenAI resource
- User-assigned managed identity for the AI analyser
- Federated identity credential for the analyser service account
- Azure RBAC for OpenAI access
- ACR pull permission for the AKS kubelet identity

### Configure variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`.

```hcl
subscription_id = "00000000-0000-0000-0000-000000000000"
location        = "eastus2"
resource_prefix = "aks-sre"
project_name    = "ai-sre"

openai_model_name    = "gpt-4.1-mini"
openai_model_version = "2025-04-14"
```

Model availability changes by region and account. The Azure OpenAI deployment is intentionally kept as a separate command so the project does not fail solely because a model/version is not available in the selected region.

Run:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out tfplan
terraform apply tfplan
```

### Get outputs

```bash
terraform output
```

Save these values:

- resource group
- AKS cluster
- ACR login server
- Azure Monitor workspace ID
- Log Analytics workspace ID
- Grafana endpoint
- Azure OpenAI endpoint
- analyser managed identity client ID
- incident collector public IP after deployment

## 3. Configure AKS monitoring

Managed Prometheus is enabled on AKS with Azure Monitor. Container Insights is enabled against Log Analytics.

From repo root:

```bash
./scripts/configure-monitoring.sh
```

The script also enables control plane metrics where supported.

Validate:

```bash
az aks show -g <RG> -n <AKS> --query addonProfiles.omsagent.enabled -o tsv
az aks show -g <RG> -n <AKS> --query azureMonitorProfile.metrics.enabled -o tsv
```

Get cluster credentials:

```bash
az aks get-credentials -g <RG> -n <AKS> --overwrite-existing
kubectl get nodes
```

## 4. Deploy the Azure OpenAI model

Because model availability differs by region, use the helper after checking the model/version available in your resource.

```bash
./scripts/create-openai-deployment.sh
```

Then test from your workstation with the same identity used for local development:

```bash
az login
export AZURE_OPENAI_ENDPOINT="$(terraform -chdir=infra output -raw openai_endpoint)"
export AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini"
python - <<'PY'
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
import os

provider = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
client = OpenAI(base_url=os.environ["AZURE_OPENAI_ENDPOINT"] + "openai/v1/", api_key=provider)
resp = client.responses.create(model=os.environ["AZURE_OPENAI_DEPLOYMENT"], input="Reply with: Azure OpenAI connectivity works")
print(resp.output_text)
PY
```

## 5. Build and test the Python API

The sample API intentionally has a small surface so the SRE components are easy to understand.

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn main:app --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8000/metrics
```

Generate controlled failures for the incident demo:

```bash
curl -X POST http://127.0.0.1:8000/admin/failure-mode -H 'content-type: application/json' -d '{"enabled":true}'
curl http://127.0.0.1:8000/demo
curl http://127.0.0.1:8000/metrics
```

Turn it off:

```bash
curl -X POST http://127.0.0.1:8000/admin/failure-mode -H 'content-type: application/json' -d '{"enabled":false}'
```

## 6. Build containers

```bash
az acr login --name <ACR_NAME>

docker build -t <ACR_LOGIN_SERVER>/sre-api:1.0.0 ./app
docker build -t <ACR_LOGIN_SERVER>/incident-collector:1.0.0 ./incident-collector
docker build -t <ACR_LOGIN_SERVER>/ai-analyser:1.0.0 ./ai-analyser

docker push <ACR_LOGIN_SERVER>/sre-api:1.0.0
docker push <ACR_LOGIN_SERVER>/incident-collector:1.0.0
docker push <ACR_LOGIN_SERVER>/ai-analyser:1.0.0
```

## 7. Deploy with Helm

Create a namespace:

```bash
kubectl create namespace sre --dry-run=client -o yaml | kubectl apply -f -
```

Install the API:

```bash
helm upgrade --install sre-api ./charts/sre-api \
  --namespace sre \
  --set image.repository=<ACR_LOGIN_SERVER>/sre-api \
  --set image.tag=1.0.0
```

Install the collector and analyser deployments using the same chart values or split them into dedicated charts later. For the complete demo, the chart creates the three workloads.

Get pods and services:

```bash
kubectl get pods -n sre
kubectl get svc -n sre
kubectl get hpa -n sre
kubectl get pdb -n sre
```

## 8. Verify Workload Identity

The analyser service account is annotated with the client ID of the user-assigned managed identity.

```bash
kubectl get sa ai-analyser -n sre -o yaml
kubectl exec -n sre deploy/ai-analyser -- env | grep AZURE_
```

The expected injected environment variables include:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_FEDERATED_TOKEN_FILE
```

The AKS Workload Identity pattern uses the OIDC issuer, a Kubernetes service account and a federated identity credential. The `api://AzureADTokenExchange` audience is important for direct federation.

## 9. Prometheus scraping

The API pods include Prometheus scrape annotations:

```yaml
prometheus.io/scrape: "true"
prometheus.io/path: /metrics
prometheus.io/port: "8000"
```

Validate metrics exist:

```bash
kubectl port-forward -n sre svc/sre-api 8000:8000
curl http://127.0.0.1:8000/metrics
```

The Azure Monitor managed service for Prometheus can scrape Kubernetes workload metrics. In Grafana, connect the Azure Monitor workspace as a Prometheus data source.

## 10. Grafana dashboard

Use Azure Managed Grafana and connect the Azure Monitor workspace. Build these panels:

1. API request rate
2. API error rate
3. P95 latency
4. CPU per pod
5. Memory per pod
6. Pod restarts
7. Ready replicas versus desired replicas
8. HPA desired replicas
9. Kubernetes warning events

Starter PromQL examples:

```promql
sum(rate(http_requests_total[5m]))
```

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
```

```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## 11. Create Azure Monitor alerts

Create alerts for:

- HTTP 5xx rate above 5 percent for 5 minutes
- Readiness failures
- Container restarts above threshold
- CPU above 80 percent for 10 minutes
- Pod unavailable or HPA saturation

For the incident demo, the most useful alert is HTTP 5xx rate.

Create an Action Group that calls the collector webhook. The demo collector exposes `/api/v1/alerts`.

Because an AKS LoadBalancer address is created after deployment, create the Action Group after you know the collector public address. For production, put the collector behind a managed ingress/API gateway and require authenticated webhook delivery.

## 12. Incident Collector

The collector performs four jobs:

1. Accept the alert payload.
2. Extract the affected workload and severity.
3. Collect recent Log Analytics entries.
4. Collect Kubernetes events and metric context.
5. Forward the evidence package to the AI analyser.

Test it manually:

```bash
curl -X POST http://<COLLECTOR_IP>/api/v1/alerts \
  -H 'content-type: application/json' \
  -d @examples/sample-alert.json
```

The collector stores a simple in-memory incident state for the lab. For production, replace this with Cosmos DB, Azure Table Storage, SQL or another durable store.

## 13. AI Incident Analyser

The analyser receives structured evidence instead of a raw unbounded prompt. Its system prompt forces the model to return:

- incident summary
- suspected root cause
- confidence
- evidence
- immediate mitigation
- long-term fix
- rollback/runbook steps
- safety notes

The model is not allowed to claim that an action was executed.

Environment variables:

```text
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
```

Test:

```bash
curl -X POST http://<ANALYSER_IP>/api/v1/analyse \
  -H 'content-type: application/json' \
  -d '{
    "incident_id":"INC-1001",
    "alert":{"name":"High5xx","severity":"Sev2"},
    "logs":[{"time":"2026-09-12T09:10:00Z","message":"Readiness probe failed"}],
    "metrics":{"error_rate":"0.31","restarts":"6"},
    "events":[{"type":"Warning","reason":"BackOff","message":"Back-off restarting failed container"}]
  }'
```

## 14. Human approval

Approval is deliberately separate.

```bash
curl -X POST http://<ANALYSER_IP>/api/v1/incidents/INC-1001/approve \
  -H 'content-type: application/json' \
  -d '{"approved_by":"engineer@contoso.com","comment":"Verified deployment regression"}'
```

The approved result can be handed to a manual Azure DevOps remediation pipeline or an Azure Automation/Logic App workflow later. Keep execution behind RBAC and an approval gate.

## 15. Azure DevOps pipeline

Import `.azuredevops/azure-pipelines.yml` into Azure DevOps.

Recommended service connections:

- Azure Resource Manager service connection using Workload Identity Federation
- ACR authentication through AzureCLI task using the service connection

Pipeline stages:

```text
Validate
  Terraform fmt/validate
  Python tests
  Helm lint

Build
  Build app images
  Trivy scan
  Push to ACR

Deploy
  kubectl credentials
  Helm upgrade
  smoke test
```

Run:

```bash
git add .
git commit -m "Initial AI AKS SRE platform"
git push -u origin feature/ai-aks-sre
```

## 16. Incident demo from end to end

### Step A: break the application

```bash
kubectl -n sre exec deploy/sre-api -- \
  sh -c 'curl -s -X POST http://127.0.0.1:8000/admin/failure-mode -H "content-type: application/json" -d "{\"enabled\":true}"'
```

### Step B: generate traffic

```bash
for i in $(seq 1 100); do curl -s -o /dev/null http://<API_IP>/demo; done
```

### Step C: verify the alert condition

Check Grafana and Azure Monitor.

### Step D: Azure Monitor fires the Action Group

The collector receives the alert and gathers evidence.

### Step E: AI produces RCA

Example structured output:

```json
{
  "severity": "Sev2",
  "summary": "API error rate increased after the application was placed into failure mode.",
  "suspected_root_cause": "Application-level failure rather than node or cluster capacity pressure.",
  "confidence": 0.94,
  "evidence": [
    "5xx rate increased",
    "No corresponding node pressure",
    "Application logs show repeated request failures"
  ],
  "recommended_runbook": [
    "Confirm error-rate alert and affected deployment",
    "Compare current image with previous successful release",
    "Roll back only after change correlation is confirmed",
    "Disable failure mode and verify health probes"
  ],
  "safety_notes": [
    "No remediation command was executed by the AI"
  ]
}
```

### Step F: engineer reviews and approves

The engineer confirms the evidence and approves the runbook.

### Step G: execute remediation manually

Run the approved command through a controlled process, for example:

```bash
helm history sre-api -n sre
helm rollback sre-api <REVISION> -n sre
kubectl rollout status deployment/sre-api -n sre
```

### Step H: verify recovery

```bash
kubectl get pods -n sre
kubectl get hpa -n sre
curl http://<API_IP>/healthz
```

## 17. Common issues and fixes

### Terraform provider or schema errors

Symptom:

```text
Unsupported argument
```

Fix:

```bash
terraform version
terraform providers
terraform init -upgrade
terraform validate
```

Pin provider versions and run CI validation before apply.

### Azure OpenAI 401/403 from AKS

Check:

```bash
kubectl exec -n sre deploy/ai-analyser -- env | grep AZURE_
```

Then verify the identity and role assignment. The managed identity needs an Azure RBAC role such as `Cognitive Services OpenAI User` at the Azure OpenAI resource scope.

Also verify the federated credential subject exactly matches:

```text
system:serviceaccount:sre:ai-analyser
```

Allow a short propagation window after the federated credential is created.

### AADSTS70021 / federated credential not found

Check:

- OIDC issuer URL
- service account namespace/name
- client ID annotation
- audience `api://AzureADTokenExchange`
- tenant ID

### ImagePullBackOff

Check ACR pull permission:

```bash
az role assignment list \
  --scope $(az acr show -n <ACR_NAME> --query id -o tsv) \
  --include-inherited \
  --query "[?roleDefinitionName=='AcrPull']" -o table
```

Restart the deployment if the role was added just before rollout.

### HPA shows unknown CPU

Check resource requests and metrics:

```bash
kubectl describe hpa sre-api -n sre
kubectl top pods -n sre
```

HPA utilization depends on container resource requests. A missing metrics provider or missing requests causes the common `unknown` state.

### Prometheus has no application metrics

Check scrape annotations and that `/metrics` is reachable:

```bash
kubectl get pod -n sre -o yaml | grep -A10 prometheus.io
kubectl port-forward -n sre svc/sre-api 8000:8000
curl http://127.0.0.1:8000/metrics
```

### Collector cannot query Log Analytics

The analyser/collector identity needs a role that permits querying the workspace. Use a least-privilege monitoring reader role for the environment and verify the workspace ID is the Workspace ID, not just the resource ID.

### Collector receives alert but analysis fails

Look at:

```bash
kubectl logs deploy/incident-collector -n sre --tail=200
kubectl logs deploy/ai-analyser -n sre --tail=200
```

Check:

- Azure OpenAI endpoint
- deployment name
- Entra authentication
- network path from AKS to Azure OpenAI
- model capacity/quota
- malformed incident evidence JSON

### Pods restart continuously

```bash
kubectl describe pod -n sre <POD>
kubectl logs -n sre <POD> --previous
kubectl get events -n sre --sort-by=.lastTimestamp
```

Separate application crash loops from probe failures. If the readiness probe is failing but the container itself is healthy, inspect path, port and startup time.

### Grafana cannot read Prometheus data

Make sure the Azure Monitor workspace is connected to the Azure Managed Grafana workspace and that the Grafana managed identity has the required monitoring data reader permissions.

## 18. Production hardening after the lab

Replace the demo's public HTTP collector with a protected HTTPS ingress or API gateway.

Replace in-memory incidents with durable state.

Use Key Vault for non-federated secrets where needed.

Add Azure Policy for AKS and container governance.

Add Defender for Containers or an approved scanner alongside Trivy.

Add a real approval workflow through Azure DevOps Environments, Logic Apps or another ITSM system.

Add runbook versioning and audit records.

Add model-output validation using JSON Schema/Pydantic before the result is shown to an engineer.

Add prompt-injection defenses by treating logs and Kubernetes events as untrusted data.

## 19. Skills demonstrated in the project

This project is suitable as a senior DevOps/SRE portfolio project because it demonstrates:

- Azure networking and identity
- AKS cluster operations
- Kubernetes deployment and scaling
- Helm
- Terraform
- Azure DevOps CI/CD
- ACR
- Workload Identity
- Prometheus and Grafana
- Log Analytics and Azure Monitor
- Python automation
- Azure OpenAI integration
- Incident response and RCA
- Human-in-the-loop automation
- Security and governance

## Official references

- AKS Workload Identity: https://learn.microsoft.com/azure/aks/workload-identity-deploy-cluster
- AKS monitoring and managed Prometheus: https://learn.microsoft.com/azure/azure-monitor/containers/kubernetes-monitoring-enable
- Azure Managed Grafana with Azure Monitor workspace: https://learn.microsoft.com/azure/managed-grafana/how-to-connect-azure-monitor-workspace
- Azure OpenAI Responses API: https://learn.microsoft.com/azure/ai-services/openai/quickstart
- Azure Monitor Query Python library: https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme
- AKS HPA: https://learn.microsoft.com/azure/aks/horizontal-pod-autoscaler

## 20. Azure DevOps variable setup

Before running the pipeline, create these variables in the pipeline or variable group:

```text
azureServiceConnection = sc-azure-aks-sre
acrName = <Terraform ACR name>
azureOpenAIDeployment = sre-analyser
```

Set `sc-azure-aks-sre` to the Azure Resource Manager service connection used by the pipeline. For a cleaner production setup, use workload identity federation rather than a client secret.

For the first run, keep `applyInfra` false if Terraform infrastructure already exists. Use the Infrastructure stage only when you intentionally want the pipeline to create/update Azure resources and require the environment approval.
