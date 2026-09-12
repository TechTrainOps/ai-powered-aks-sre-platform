#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="$(terraform -chdir="$ROOT_DIR/infra" output -raw resource_group_name)"
AKS="$(terraform -chdir="$ROOT_DIR/infra" output -raw aks_name)"
ACR="$(terraform -chdir="$ROOT_DIR/infra" output -raw acr_login_server)"
OAIE="$(terraform -chdir="$ROOT_DIR/infra" output -raw openai_endpoint)"
ANALYSER_ID="$(terraform -chdir="$ROOT_DIR/infra" output -raw analyser_client_id)"
COLLECTOR_ID="$(terraform -chdir="$ROOT_DIR/infra" output -raw collector_client_id)"
LAW_ID="$(terraform -chdir="$ROOT_DIR/infra" output -raw log_analytics_workspace_customer_id)"

az aks get-credentials -g "$RG" -n "$AKS" --overwrite-existing
kubectl create namespace sre --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install sre-api "$ROOT_DIR/charts/sre-api" \
  --namespace sre \
  --set image.repository="$ACR/sre-api" \
  --set image.tag="${IMAGE_TAG:-1.0.0}" \
  --set collectorImage.repository="$ACR/incident-collector" \
  --set collectorImage.tag="${IMAGE_TAG:-1.0.0}" \
  --set analyserImage.repository="$ACR/ai-analyser" \
  --set analyserImage.tag="${IMAGE_TAG:-1.0.0}" \
  --set azure.openaiEndpoint="$OAIE" \
  --set azure.openaiDeployment="${AZURE_OPENAI_DEPLOYMENT:-sre-analyser}" \
  --set azure.logWorkspaceId="$LAW_ID" \
  --set azure.analyserClientId="$ANALYSER_ID" \
  --set azure.collectorClientId="$COLLECTOR_ID"

kubectl rollout status deployment/sre-api -n sre --timeout=180s
kubectl rollout status deployment/incident-collector -n sre --timeout=180s
kubectl rollout status deployment/ai-analyser -n sre --timeout=180s
