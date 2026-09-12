#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="$(terraform -chdir="$ROOT_DIR/infra" output -raw resource_group_name)"
AKS="$(terraform -chdir="$ROOT_DIR/infra" output -raw aks_name)"
LAW_ID="$(terraform -chdir="$ROOT_DIR/infra" output -raw log_analytics_workspace_id)"
AMW_ID="$(terraform -chdir="$ROOT_DIR/infra" output -raw monitor_workspace_id)"

az aks enable-addons \
  --resource-group "$RG" \
  --name "$AKS" \
  --addons monitoring \
  --workspace-resource-id "$LAW_ID"

az aks update \
  --resource-group "$RG" \
  --name "$AKS" \
  --enable-azure-monitor-metrics \
  --azure-monitor-workspace-resource-id "$AMW_ID"

az aks update \
  --resource-group "$RG" \
  --name "$AKS" \
  --enable-control-plane-metrics || echo "Control-plane metrics flag was not accepted; continue with workload metrics."

echo "Monitoring configured for $AKS"
