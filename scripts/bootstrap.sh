#!/usr/bin/env bash
set -euo pipefail

command -v az >/dev/null || { echo "Azure CLI is required"; exit 1; }
command -v kubectl >/dev/null || { echo "kubectl is required"; exit 1; }
command -v helm >/dev/null || { echo "Helm is required"; exit 1; }
command -v terraform >/dev/null || { echo "Terraform is required"; exit 1; }
command -v docker >/dev/null || { echo "Docker is required"; exit 1; }

az account show >/dev/null || az login

echo "Prerequisites found."
echo "Next: copy infra/terraform.tfvars.example to infra/terraform.tfvars and run terraform init/plan/apply."
