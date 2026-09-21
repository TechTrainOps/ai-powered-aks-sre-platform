````markdown
# Deployment Guide

This document describes how to provision the Azure infrastructure, build the application containers, push them to Azure Container Registry (ACR), and deploy the workloads to Azure Kubernetes Service (AKS) using Terraform, Azure DevOps, and Helm.

The deployment process is designed around three application components:

```text
sre-api
incident-collector
ai-analyser
````

The overall deployment flow is:

```text
GitHub
   |
   v
Azure DevOps Pipeline
   |
   +--> Terraform Validation
   |
   +--> Application Tests
   |
   +--> Helm Validation
   |
   +--> Container Build
   |
   +--> Security Scan
   |
   +--> Push Images to ACR
   |
   +--> Helm Deployment to AKS
   |
   +--> Rollout Validation
   |
   v
AKS
```

---

# 1. Prerequisites

The deployment environment requires:

```text
Azure CLI
Terraform
kubectl
Helm
Git

Docker
Required on the CI build agent used for container image build/scan.
The Windows deployment agent does not require Docker.
```

The Azure DevOps pipeline authenticates to Azure using an
Azure DevOps workload identity federation service connection.

Local administrative commands such as kubectl and Azure CLI
require the operator to authenticate to the target subscription
and AKS cluster.

---

# 2. Azure Resources

The project uses Terraform to provision the required Azure resources.

The platform includes resources such as:

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
Azure Storage
Private Endpoint resources
```

The resources are deployed in the configured Azure region.

---

# 3. Terraform Backend

Terraform state is stored remotely in Azure Storage.

The backend configuration is:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-ai-aks-sre-tfstate"
    storage_account_name = "staiakssre2026"
    container_name       = "tfstate"
    key                  = "ai-aks-sre.tfstate"
    use_oidc              = true
    use_azuread_auth      = true
  }
}
```

The backend uses Azure AD authentication and workload identity rather than a storage access key.

The Terraform state storage is separate from storage used by the application.

---

# 4. Azure Authentication

The Azure DevOps deployment uses a workload identity federation based service connection.

Terraform authentication is configured using environment variables similar to:

```powershell
$env:ARM_USE_OIDC = "true"
$env:ARM_USE_AZUREAD = "true"
$env:ARM_CLIENT_ID = $env:servicePrincipalId
$env:ARM_TENANT_ID = $env:tenantId
$env:ARM_OIDC_AZURE_SERVICE_CONNECTION_ID = $env:AZURESUBSCRIPTION_SERVICE_CONNECTION_ID
```

This allows Terraform to authenticate to Azure without storing a client secret in the repository.

---

# 5. Terraform Deployment

Navigate to the Terraform directory:

```powershell
cd .\terraform
```

Initialize the Terraform working directory:

```powershell
terraform init
```

Validate the configuration:

```powershell
terraform validate
```

Create the execution plan:

```powershell
terraform plan
```

Review the plan before applying the infrastructure.

Apply the configuration:

```powershell
terraform apply
```

When prompted, confirm the Terraform deployment.

The expected result is that the Azure resources required by the platform are created or updated successfully.

---

# 6. Terraform Provider Registration

The required Azure resource providers must be registered before deploying resources.

The exact provider set depends on the Terraform configuration, but the platform uses Azure services including:

```text
Microsoft.ContainerService
Microsoft.ContainerRegistry
Microsoft.CognitiveServices
Microsoft.Monitor
Microsoft.Dashboard
Microsoft.Storage
Microsoft.Network
Microsoft.ManagedIdentity
Microsoft.OperationalInsights
```

Provider registration can be performed through Azure CLI when required.

Example:

```powershell
az provider register --namespace Microsoft.ContainerService
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.Monitor
az provider register --namespace Microsoft.Dashboard
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Network
az provider register --namespace Microsoft.ManagedIdentity
az provider register --namespace Microsoft.OperationalInsights
```

Verify registration:

```powershell
az provider show --namespace Microsoft.ContainerService --query registrationState
az provider show --namespace Microsoft.ContainerRegistry --query registrationState
az provider show --namespace Microsoft.CognitiveServices --query registrationState
```

The expected state is:

```text
Registered
```

---

# 7. Terraform Outputs

After Terraform deployment, retrieve the outputs:

```powershell
terraform output
```

Important values include:

```text
Azure OpenAI endpoint
Azure OpenAI deployment name
Analyser client ID
Collector client ID
```

These values are used by the deployment pipeline and application configuration.

---

# 8. AKS Access

After AKS is created, obtain cluster credentials:

```powershell
az aks get-credentials `
  --resource-group <AKS_RESOURCE_GROUP> `
  --name <AKS_CLUSTER_NAME> `
  --overwrite-existing
```

Verify access:

```powershell
kubectl get nodes
```

The cluster nodes should be returned successfully.

---

# 9. Kubernetes Namespace

The application workloads are deployed into the `sre` namespace.

The Helm deployment creates the namespace automatically using:

```text
--create-namespace
```

The namespace can also be verified with:

```powershell
kubectl get namespace sre
```

---

# 10. Azure Container Registry

The three application images are stored in Azure Container Registry:

```text
sre-api
incident-collector
ai-analyser
```

The image format is:

```text
<ACR_LOGIN_SERVER>/sre-api:<BUILD_ID>
<ACR_LOGIN_SERVER>/incident-collector:<BUILD_ID>
<ACR_LOGIN_SERVER>/ai-analyser:<BUILD_ID>
```

Example:

```text
<ACR_LOGIN_SERVER>/sre-api:<BUILD_ID>
<ACR_LOGIN_SERVER>/incident-collector:<BUILD_ID>
<ACR_LOGIN_SERVER>/ai-analyser:<BUILD_ID>
```

The build ID is generated by Azure DevOps.

---

# 11. Building the Application Images

The project contains three independently containerized components:

```text
app / sre-api
incident-collector
ai-analyser
```

The Docker build process creates an image for each component.

A representative build command for the API is:

```powershell
docker build -t <ACR_LOGIN_SERVER>/sre-api:<BUILD_ID> .
```

The Incident Collector is built similarly:

```powershell
docker build -t <ACR_LOGIN_SERVER>/incident-collector:<BUILD_ID> .\incident-collector
```

The AI Analyser is built similarly:

```powershell
docker build -t <ACR_LOGIN_SERVER>/ai-analyser:<BUILD_ID> .\ai-analyser
```

The Azure DevOps pipeline performs the actual image build process.

---

# 12. Pushing Images to ACR

Authenticate to ACR:

```powershell
az acr login --name <ACR_NAME>
```

Push the application images:

```powershell
docker push <ACR_LOGIN_SERVER>/sre-api:<BUILD_ID>
docker push <ACR_LOGIN_SERVER>/incident-collector:<BUILD_ID>
docker push <ACR_LOGIN_SERVER>/ai-analyser:<BUILD_ID>
```

The Azure DevOps pipeline performs these operations automatically as part of CI/CD.

---

# 13. Helm Chart

The Kubernetes workloads are packaged using the Helm chart:

```text
charts/
└── sre-api/
```

The chart manages:

```text
sre-api Deployment
incident-collector Deployment
ai-analyser Deployment
Services
ServiceAccounts
Role
RoleBinding
HPA
PDB
PodMonitor
Alert-related configuration
Application configuration
```

---

# 14. Helm Validation

Before deploying the chart, validate the templates:

```powershell
helm lint .\charts\sre-api
```

Render the templates locally:

```powershell
helm template sre-api .\charts\sre-api `
  --namespace sre
```

This allows the generated Kubernetes manifests to be reviewed before deployment.

---

# 15. Helm Deployment

The Azure DevOps pipeline uses:

```powershell
helm upgrade --install
```

The deployment provides:

```text
Application image
Collector image
AI Analyser image
Azure OpenAI endpoint
Azure OpenAI deployment
Analyser identity
Metrics configuration
Collector webhook configuration
```

The deployment command follows this pattern:

```powershell
helm upgrade --install sre-api .\charts\sre-api `
  --namespace "$(namespace)" `
  --create-namespace `
  --set image.repository="$(acrLoginServer)/sre-api" `
  --set image.tag="$(Build.BuildId)" `
  --set collector.enabled=true `
  --set collectorImage.repository="$(acrLoginServer)/incident-collector" `
  --set collectorImage.tag="$(Build.BuildId)" `
  --set analyser.enabled=true `
  --set analyserImage.repository="$(acrLoginServer)/ai-analyser" `
  --set analyserImage.tag="$(Build.BuildId)" `
  --set-string azure.openaiEndpoint="$(openAiEndpoint)" `
  --set-string azure.openaiDeployment="$(openAiDeployment)" `
  --set-string azure.analyserClientId="$(analyserClientId)" `
  --set metrics.enabled=true `
  --set-string collector.webhookToken="$env:COLLECTOR_WEBHOOK_TOKEN" `
  --force-conflicts `
  --wait `
  --timeout 10m
```

Sensitive values such as the webhook token are supplied through Azure DevOps secret variables.

---

# 16. Helm Server-Side Apply Conflict Handling

The remediation system can modify Kubernetes Deployment fields that are normally managed by Helm.

During rollback testing, the `sre-api` image field became associated with the remediation field manager.

The next normal Helm deployment initially encountered a Server-Side Apply conflict:

```text
conflict with "OpenAPI-Generator"

.spec.template.spec.containers[name="sre-api"].image
```

The deployment was updated to include:

```text
--force-conflicts
```

This allows Helm to reclaim ownership of the conflicting field during the next normal deployment.

The validated lifecycle is:

```text
Normal CI/CD
     |
     v
Helm owns image
     |
     v
Incident occurs
     |
     v
Rollback runbook
     |
     v
Remediation updates image
     |
     v
Application recovery
     |
     v
Next CI/CD deployment
     |
     v
Helm --force-conflicts
     |
     v
Helm owns image again
```

---

# 17. Helm Deployment Exit Handling

The PowerShell deployment task explicitly checks the Helm exit code.

The pipeline uses:

```powershell
if ($LASTEXITCODE -ne 0) {
  throw "Helm deployment failed with exit code $LASTEXITCODE."
}
```

This prevents a failed Helm deployment from being incorrectly reported as successful.

The success message is printed only after Helm exits successfully.

---

# 18. Deployment Rollout Validation

After Helm deployment, the pipeline verifies each Deployment.

### sre-api

```powershell
kubectl rollout status `
  deployment/sre-api `
  -n sre `
  --timeout=300s
```

### Incident Collector

```powershell
kubectl rollout status `
  deployment/incident-collector `
  -n sre `
  --timeout=300s
```

### AI Analyser

```powershell
kubectl rollout status `
  deployment/ai-analyser `
  -n sre `
  --timeout=300s
```

A successful rollout means the requested Deployment update has completed successfully.

---

# 19. Verify Pods

List all application pods:

```powershell
kubectl get pods -n sre -o wide
```

Expected workloads include:

```text
sre-api
incident-collector
ai-analyser
```

---

# 20. Verify Deployments

Check deployed images and replica counts:

```powershell
kubectl get deployments -n sre `
  -o custom-columns="NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision,READY:.status.readyReplicas,DESIRED:.spec.replicas"
```

Example expected state:

```text
NAME                 IMAGE
ai-analyser          <ACR>/ai-analyser:<BUILD_ID>
incident-collector   <ACR>/incident-collector:<BUILD_ID>
sre-api              <ACR>/sre-api:<BUILD_ID>
```

---

# 21. Verify HPA

Check the Horizontal Pod Autoscaler:

```powershell
kubectl get hpa -n sre
```

The configured `sre-api` HPA uses:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

A healthy example:

```text
NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS
sre-api   Deployment/sre-api   cpu: 1%/70%   2         8         2
```

---

# 22. Verify Application Health

Find an `sre-api` pod:

```powershell
$SrePod = kubectl get pods -n sre -l app=sre-api -o jsonpath="{.items[0].metadata.name}"
Write-Host "SrePod=$SrePod"
```

Check health:

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/healthz'); print('healthz=',r.status); print(r.read().decode())"
```

Expected:

```text
healthz= 200
{"status":"healthy"}
```

Check readiness:

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/readyz'); print('readyz=',r.status); print(r.read().decode())"
```

Expected:

```text
readyz= 200
{"status":"ready"}
```

Check the application endpoint:

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/demo'); print('demo=',r.status); print(r.read().decode())"
```

Expected:

```text
demo= 200
{"message":"request succeeded"}
```

---

# 23. Verify Prometheus Metrics

Check that the metrics endpoint is available:

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/metrics'); print('metrics=',r.status)"
```

Expected:

```text
metrics= 200
```

The application metrics include:

```text
http_requests_total
http_request_duration_seconds
```

---

# 24. Verify Managed Prometheus

The `sre-api` metrics are collected through Azure Managed Prometheus.

Verify that the corresponding metrics are available in the Azure Monitor / Managed Prometheus environment.

The project also uses a PodMonitor to discover the application metrics endpoint.

---

# 25. Verify Grafana

Azure Managed Grafana is connected to the monitoring environment.

Verify that the SRE API dashboard displays application and Kubernetes telemetry such as:

```text
HTTP request volume
HTTP error rate
Request latency
Pod availability
Resource utilization
Application metrics
```

---

# 26. Verify Alerting

The Prometheus alert rule monitors the HTTP 5xx error rate.

The alert logic is:

```text
100 *
(
  sum(rate(http_requests_total{namespace="sre",status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{namespace="sre"}[5m]))
) > 5
```

The alert is configured with:

```text
Threshold: > 5%
Duration: 5 minutes
Severity: Sev2
```

The action group sends:

```text
Email notification
Webhook notification
```

---

# 27. Incident Collector Configuration

The Incident Collector requires configuration for:

```text
INCIDENT_NAMESPACE
COLLECTOR_WEBHOOK_TOKEN
AI_ANALYSER_URL
INCIDENT_DIR
INCIDENT_STORAGE_ACCOUNT
INCIDENT_STORAGE_CONTAINER
```

The application uses identity-based Azure authentication to access Blob Storage.

The Incident Collector also uses the Kubernetes API to collect:

```text
Pods
Pod logs
Events
Deployments
ReplicaSets
```

---

# 28. AI Analyser Configuration

The AI Analyser is configured with the Azure OpenAI endpoint and deployment name.

The deployment configuration includes values such as:

```text
Azure OpenAI endpoint
Azure OpenAI deployment
Analyser identity
```

The model deployment is managed through Terraform.

The deployed model configuration used by the project is:

```text
Model: gpt-5.4-mini
Model version: 2026-03-17
SKU: GlobalStandard
Capacity: 4000
Version upgrade option: NoAutoUpgrade
```

---

# 29. Re-deployment

A normal application update is performed by running the Azure DevOps pipeline again.

The pipeline generates a new build ID.

For example:

```text
715
```

may be followed by:

```text
716
```

The pipeline then:

```text
Builds new images
     |
     v
Scans images
     |
     v
Pushes images to ACR
     |
     v
Runs Helm upgrade
     |
     v
Waits for rollout
     |
     v
Validates deployments
```

The Kubernetes Deployment image is updated to the new build.

---

# 30. Rollback Deployment Behavior

Rollback is handled by the Incident Collector rather than manually selecting an arbitrary image.

The rollback process is:

```text
Current Deployment
       |
       v
Current revision
       |
       v
ReplicaSet history
       |
       v
Previous revision
       |
       v
Previous pod template
       |
       v
Deployment update
       |
       v
Rollout
       |
       v
Application verification
```

The rollback runbook identifies the immediately previous Deployment revision.

---

# 31. Normal Deployment After Rollback

After rollback, the next normal CI/CD deployment can reclaim Helm ownership of the image field.

The validated process is:

```text
Deployment image: newer version
        |
        v
Controlled incident
        |
        v
Rollback runbook
        |
        v
Previous image
        |
        v
Application recovered
        |
        v
Azure DevOps pipeline
        |
        v
Helm --force-conflicts
        |
        v
New image
```

This allows rollback remediation to coexist with normal Helm-based CI/CD deployments.

---

# 32. Deployment Troubleshooting

## Helm conflict

If Helm reports:

```text
conflict with "OpenAPI-Generator"
```

for:

```text
.spec.template.spec.containers[name="sre-api"].image
```

verify the Deployment field ownership:

```powershell
kubectl get deployment sre-api -n sre -o json --show-managed-fields |
  ConvertFrom-Json |
  Select-Object -ExpandProperty metadata |
  Select-Object -ExpandProperty managedFields |
  Format-List manager,operation,time,fieldsV1
```

The Helm deployment should include:

```text
--force-conflicts
```

---

## Deployment not ready

Check:

```powershell
kubectl get pods -n sre
```

Then:

```powershell
kubectl describe deployment sre-api -n sre
```

Check pod details:

```powershell
kubectl describe pod <POD_NAME> -n sre
```

Check logs:

```powershell
kubectl logs <POD_NAME> -n sre
```

---

## Readiness failure

Check:

```powershell
kubectl get pods -n sre -l app=sre-api
```

Then test:

```text
/healthz
/readyz
```

A pod can be:

```text
Running
```

while still being:

```text
NotReady
```

because the readiness probe can fail while the process remains alive.

---

## Image pull failure

Verify the image exists:

```powershell
az acr repository list --name <ACR_NAME> --output table
```

Verify the image tags:

```powershell
az acr repository show-tags `
  --name <ACR_NAME> `
  --repository sre-api `
  --output table
```

Then inspect pod events:

```powershell
kubectl describe pod <POD_NAME> -n sre
```

---

# 33. Deployment Validation Checklist

After a successful deployment, verify:

```text
[ ] Terraform completed successfully
[ ] AKS is accessible
[ ] ACR images exist
[ ] Helm lint succeeds
[ ] Helm upgrade succeeds
[ ] sre-api rollout succeeds
[ ] incident-collector rollout succeeds
[ ] ai-analyser rollout succeeds
[ ] All expected pods are Running
[ ] sre-api healthz = 200
[ ] sre-api readyz = 200
[ ] sre-api demo = 200
[ ] HPA exists
[ ] Prometheus metrics are available
[ ] Grafana dashboard is receiving data
[ ] Alert rule exists
[ ] Incident Collector webhook is reachable
[ ] Azure OpenAI configuration is available
[ ] Incident storage is accessible
```

---

# 34. Final Deployment Architecture

The completed deployment path is:

```text
GitHub
   |
   v
Azure DevOps
   |
   +---- Terraform Validation
   |
   +---- Application Tests
   |
   +---- Helm Validation
   |
   +---- Container Build
   |
   +---- Security Scan
   |
   +---- ACR Push
   |
   +---- Helm Deploy
   |
   v
AKS
   |
   +---- sre-api
   |
   +---- incident-collector
   |
   +---- ai-analyser
   |
   +---- HPA
   |
   +---- PDB
   |
   +---- PodMonitor
   |
   v
Monitoring
   |
   +---- Managed Prometheus
   |
   +---- Azure Managed Grafana
   |
   +---- Azure Monitor
   |
   v
Incident Automation
```

---

# 35. Deployment Outcome

A successful deployment results in:

```text
sre-api              Running
incident-collector   Running
ai-analyser          Running
```

with:

```text
sre-api healthz = 200
sre-api readyz  = 200
sre-api demo    = 200
```

The platform is then ready to:

```text
Collect Metrics
     |
     v
Detect Incidents
     |
     v
Generate AI-assisted RCA
     |
     v
Request Human Approval
     |
     v
Execute Remediation
     |
     v
Verify Recovery
```

```
```
