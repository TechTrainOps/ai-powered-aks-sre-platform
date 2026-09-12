#!/usr/bin/env bash
set -euo pipefail

kubectl get nodes
kubectl get pods -n sre
kubectl get hpa -n sre
kubectl get pdb -n sre
kubectl get events -n sre --sort-by=.lastTimestamp | tail -20

API_IP="$(kubectl get svc sre-api -n sre -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
COLLECTOR_IP="$(kubectl get svc incident-collector -n sre -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"

echo "API: $API_IP"
echo "Collector: $COLLECTOR_IP"

curl --fail "http://$API_IP/healthz"
echo
curl --fail "http://$API_IP/readyz"
echo
curl --fail "http://$API_IP/metrics" | grep http_requests_total | head -5
