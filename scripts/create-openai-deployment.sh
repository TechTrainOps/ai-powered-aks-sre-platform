#!/usr/bin/env bash
set -euo pipefail

RG="$(terraform -chdir=infra output -raw resource_group_name)"
ACCOUNT="$(az cognitiveservices account list -g "$RG" --query '[?kind==`OpenAI`].name | [0]' -o tsv)"
MODEL="${OPENAI_MODEL_NAME:-gpt-4.1-mini}"
VERSION="${OPENAI_MODEL_VERSION:-2025-04-14}"
DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-sre-analyser}"
CAPACITY="${OPENAI_CAPACITY:-10}"

if [[ -z "$ACCOUNT" ]]; then
  echo "Could not find an OpenAI Cognitive Services account in $RG." >&2
  exit 1
fi

az cognitiveservices account deployment create \
  --resource-group "$RG" \
  --name "$ACCOUNT" \
  --deployment-name "$DEPLOYMENT" \
  --model-name "$MODEL" \
  --model-version "$VERSION" \
  --model-format OpenAI \
  --sku-capacity "$CAPACITY" \
  --sku-name Standard

echo "Created deployment $DEPLOYMENT for model $MODEL $VERSION"
