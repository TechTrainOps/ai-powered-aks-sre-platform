# 20-minute demo script

## 1. Show architecture

Explain the signal path from developer commit to AKS, monitoring, incident collector and AI analysis.

## 2. Show Git structure

```bash
tree -L 3
```

## 3. Show Terraform

```bash
terraform -chdir=infra output
```

Point out OIDC, Workload Identity, ACR role assignment, OpenAI role assignment and collector Log Analytics role.

## 4. Show Kubernetes controls

```bash
kubectl get deploy,svc,hpa,pdb -n sre
```

Then:

```bash
kubectl describe hpa sre-api -n sre
```

## 5. Generate the failure

```bash
API_IP=$(kubectl get svc sre-api -n sre -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl -X POST http://$API_IP/admin/failure-mode \
  -H 'content-type: application/json' \
  -d '{"enabled":true}'
for i in $(seq 1 50); do curl -s -o /dev/null http://$API_IP/demo; done
```

## 6. Investigate manually

```bash
kubectl get events -n sre --sort-by=.lastTimestamp | tail -20
kubectl logs -n sre deploy/sre-api --tail=50
```

## 7. Trigger the incident path

Post `examples/sample-alert.json` to the collector.

## 8. Show AI output

```bash
curl http://<ANALYSER_IP>/api/v1/incidents/INC-1001
```

Discuss confidence, evidence and recommended runbook.

## 9. Approve

```bash
curl -X POST http://<ANALYSER_IP>/api/v1/incidents/INC-1001/approve \
  -H 'content-type: application/json' \
  -d '{"approved_by":"engineer@contoso.com","comment":"Verified release correlation"}'
```

## 10. Recover

```bash
curl -X POST http://$API_IP/admin/failure-mode \
  -H 'content-type: application/json' \
  -d '{"enabled":false}'
```

Then verify:

```bash
curl http://$API_IP/healthz
curl http://$API_IP/readyz
```
