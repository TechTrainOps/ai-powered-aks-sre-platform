Yes. Based on everything we tested, I would keep an **interview command sheet** with two modes:

1. A **safe 5–10 minute interview demo** using the current healthy environment and the already validated incident records.
2. A **full live incident test** when you have enough time to wait for the alert.

The important thing is that you should not unnecessarily change the cluster during an interview. Your restart, scale, and rollback runbooks have already been successfully validated.

# 1. What each runbook is for

| Runbook            | Failure / Situation                                 | What it does                                                    |
| ------------------ | --------------------------------------------------- | --------------------------------------------------------------- |
| `restart-sre-api`  | Pods are Running but NotReady, readiness is failing | Restarts the Deployment and verifies recovery                   |
| `scale-sre-api`    | Application needs more/fewer replicas               | Changes replica count, verifies reconciliation and availability |
| `rollback-sre-api` | New deployment/image causes regression              | Finds previous Deployment revision and restores it              |

Your actual tested scenarios were:

```text
Restart:
Readiness failure
/readyz = 503
pods = Running but NotReady
        ↓
restart-sre-api
        ↓
recovery
```

```text
Scale:
2 replicas
        ↓
request 3 replicas
        ↓
3 replicas available
```

```text
Rollback:
sre-api:713
        ↓
deployment regression
        ↓
rollback-sre-api
        ↓
previous revision
        ↓
sre-api:712
```

---

# 2. Start the interview with the current platform state

These are the first commands I would run.

## Command 1: Show all workloads

```powershell
kubectl get deployments -n sre -o custom-columns="NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision,READY:.status.readyReplicas,DESIRED:.spec.replicas"
```

### What it does

Shows:

```text
Deployment name
Container image
Deployment revision
Ready replicas
Desired replicas
```

Your current expected state is:

```text
ai-analyser          :715   2/2
incident-collector   :715   1/1
sre-api              :715   2/2
```

This immediately demonstrates that all three application components are deployed.

---

# 3. Show HPA

```powershell
kubectl get hpa -n sre
```

### What it demonstrates

Your SRE API has:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

This lets you explain:

> The application is protected by Kubernetes HPA so normal workload growth can increase replicas automatically. The scale runbook is separate controlled remediation for an operator-approved scaling action.

---

# 4. Show the pods

```powershell
kubectl get pods -n sre -o wide
```

### What it demonstrates

This shows the actual runtime state:

```text
sre-api
incident-collector
ai-analyser
```

You can point out:

> The Incident Collector and AI Analyser themselves run inside the same AKS cluster as the monitored application.

---

# 5. Show application health

Get an SRE API pod:

```powershell
$SrePod = kubectl get pods -n sre -l app=sre-api -o jsonpath="{.items[0].metadata.name}"
Write-Host "SrePod=$SrePod"
```

Then:

### Health

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/healthz'); print('healthz=',r.status); print(r.read().decode())"
```

Expected:

```text
healthz= 200
{"status":"healthy"}
```

### Readiness

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/readyz'); print('readyz=',r.status); print(r.read().decode())"
```

Expected:

```text
readyz= 200
{"status":"ready"}
```

### Application

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/demo'); print('demo=',r.status); print(r.read().decode())"
```

Expected:

```text
demo= 200
{"message":"request succeeded"}
```

### What to tell the interviewer

> I intentionally have separate health and readiness endpoints. A pod can be alive but not ready to receive traffic. That distinction is important for the incident scenario.

---

# 6. Show Prometheus metrics

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/metrics'); print('metrics=',r.status)"
```

Expected:

```text
metrics= 200
```

### What to explain

> The FastAPI application exposes Prometheus metrics. Azure Managed Prometheus collects them, Azure Monitor evaluates the alert rule, and Grafana visualizes them.

Then open your **Azure Managed Grafana dashboard** in the browser and show the dashboard you already created.

---

# 7. Show the runbook registry

This is a very good interviewer command because it shows that remediation is based on registered actions rather than arbitrary commands.

```powershell
kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/runbooks'); print('status=',r.status); print(r.read().decode())"
```

You should see the registered runbooks:

```text
restart-sre-api
scale-sre-api
rollback-sre-api
```

### Explain

> The AI analyser doesn't generate arbitrary Kubernetes commands. The system selects from registered runbooks, and execution requires human approval.

That is an important architectural point.

---

# 8. Show an already completed restart incident

For an interview, this is much better than making the interviewer wait five minutes for Azure Monitor.

Your successfully tested restart incident is:

```text
0c19911e-9124-424a-9cbc-1fcaedb3b7f6
```

Run:

```powershell
$IncidentId = "0c19911e-9124-424a-9cbc-1fcaedb3b7f6"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

This will show:

```text
Alert
Evidence
AI analysis
Approval
Remediation
Verification
```

The final result from your actual test was:

```text
status = Remediated

runbook = restart-sre-api

remediation.status = Succeeded

rollout.success = true

verification.success = true

healthz = 200
readyz = 200
demo = 200
```

This is one of the strongest commands to show the interviewer because it demonstrates the entire incident lifecycle from a single record.

---

# 9. Show the scale runbook result

Your successful scale incident was:

```text
18df1613-1cea-4f70-b2f7-599e37f8d0a7
```

Run:

```powershell
$IncidentId = "18df1613-1cea-4f70-b2f7-599e37f8d0a7"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

The successful test demonstrated:

```text
previous replicas = 2
requested replicas = 3
observed replicas = 3
available replicas = 3
unavailable replicas = 0
```

and:

```text
healthz = 200
readyz = 200
demo = 200
```

### What to tell the interviewer

> The scale runbook doesn't simply patch the Deployment and assume success. It waits for Kubernetes to reconcile the requested replica count, verifies availability, and then verifies the application.

That is an important engineering detail.

---

# 10. Show the rollback runbook result

Your successful rollback incident was:

```text
a192c306-e78c-4209-b117-86259804c7d9
```

Run:

```powershell
$IncidentId = "a192c306-e78c-4209-b117-86259804c7d9"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

That incident demonstrated:

```text
Current revision: 32
Target revision: 31

Current image:
sre-api:713

Target image:
sre-api:712

Final revision:
33

Final image:
sre-api:712
```

Then:

```text
healthz = 200
readyz = 200
demo = 200
```

### What to explain

> The rollback runbook doesn't ask the operator or AI to provide an arbitrary image. It looks at Kubernetes ReplicaSet history and determines the immediately previous Deployment revision.

That's a very good design point to highlight.

---

# 11. Show the current Helm ownership

This is useful if the interviewer asks about the problem you solved between Helm and remediation.

```powershell
kubectl get deployment sre-api -n sre -o json --show-managed-fields | ConvertFrom-Json | Select-Object -ExpandProperty metadata | Select-Object -ExpandProperty managedFields | ForEach-Object { "$($_.manager): " + ($_.fieldsV1 | ConvertTo-Json -Depth 20 -Compress) } | Select-String '"f:image"'
```

Your current output showed:

```text
helm: ... "f:image":{} ...
```

### Explain

> The remediation runbook can temporarily modify fields normally managed by Helm. Kubernetes Server-Side Apply tracks field ownership. We resolved the conflict by using Helm's `--force-conflicts` during the next normal CI/CD deployment, and Helm regained ownership of the image field.

This shows real Kubernetes troubleshooting experience.

---

# 12. If you want to do the restart demo LIVE

This is the one I'd actually demonstrate live if the interviewer has enough time.

## Step A: Get the current pods

```powershell
kubectl get pods -n sre -l app=sre-api
```

Explain:

> Both pods are healthy right now.

---

## Step B: Introduce controlled failure

This is the exact command that worked during your final test:

```powershell
kubectl get pods -n sre -l app=sre-api -o jsonpath="{range .items[*]}{.metadata.name}{'\n'}{end}" | ForEach-Object {
  $pod = $_
  Write-Host "Enabling failure mode on $pod"
  kubectl exec $pod -n sre -- python -c "import json,urllib.request; data=json.dumps({'enabled':True}).encode(); req=urllib.request.Request('http://127.0.0.1:8000/admin/failure-mode',data=data,headers={'Content-Type':'application/json'},method='POST'); r=urllib.request.urlopen(req); print(r.status); print(r.read().decode())"
}
```

Expected:

```text
200
{"failure_mode":true}
```

for both pods.

---

## Step C: Show the failure

```powershell
kubectl get pods -n sre -l app=sre-api
```

Expected:

```text
0/1 Running
0/1 Running
```

Then check readiness:

```powershell
kubectl exec $SrePod -n sre -- python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8000); c.request('GET','/readyz'); r=c.getresponse(); print('readyz=',r.status); print(r.read().decode()); c.close()"
```

Expected:

```text
readyz= 503
{"detail":"failure mode enabled"}
```

### Explain

> The application process is still alive, so the pods remain Running. But readiness is failing, so Kubernetes considers them NotReady.

---

# 13. Wait for the alert

Your alert rule requires:

```text
5xx > 5%
for 5 minutes
```

So for the full live incident test, allow roughly **6–7 minutes** for alert evaluation and incident creation.

After that, retrieve the newest incident:

```powershell
kubectl exec deployment/incident-collector -n sre -- python -c "from azure.identity import DefaultAzureCredential; from azure.storage.blob import BlobServiceClient; c=BlobServiceClient('https://staiakssreinc2026.blob.core.windows.net',credential=DefaultAzureCredential()).get_container_client('incidents'); b=sorted(c.list_blobs(),key=lambda x:x.last_modified,reverse=True); [print(x.name,x.last_modified) for x in b[:5]]"
```

Take the newest incident ID.

Then:

```powershell
$IncidentId = "<NEW_INCIDENT_ID>"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

This shows the AI analysis and evidence.

---

# 14. Approve restart

Once the incident is in `ApprovalPending`, use:

```powershell
$IncidentId = "<NEW_INCIDENT_ID>"

kubectl exec deployment/incident-collector -n sre -- python -c "import json,urllib.request; data=json.dumps({'runbook':'restart-sre-api','parameters':{},'approved_by':'shakir'}).encode(); req=urllib.request.Request('http://127.0.0.1:8080/incidents/$IncidentId/approve',data=data,headers={'Content-Type':'application/json'},method='POST'); r=urllib.request.urlopen(req); print('status=',r.status); print(r.read().decode())"
```

Expected:

```text
status= 200
```

and:

```text
"status":"approved"
```

---

# 15. Execute restart

This is the exact remediation command that worked:

```powershell
kubectl exec deployment/incident-collector -n sre -- python -c "import json,urllib.request; req=urllib.request.Request('http://127.0.0.1:8080/incidents/$IncidentId/remediate',data=b'{}',headers={'Content-Type':'application/json'},method='POST'); r=urllib.request.urlopen(req); print('status=',r.status); print(r.read().decode())"
```

Expected:

```text
status= 200
```

and:

```text
"status":"Remediated"
```

with:

```text
"success":true
"rollout":{"success":true}
"verification":{"success":true}
```

---

# 16. Verify the restarted deployment

```powershell
kubectl get deployment sre-api -n sre -o custom-columns="NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision,READY:.status.readyReplicas,DESIRED:.spec.replicas"
```

Then:

```powershell
kubectl get pods -n sre -l app=sre-api -o wide
```

Expected:

```text
2/2 Running
2/2 Running
```

---

# 17. Verify application recovery

```powershell
$SrePod = kubectl get pods -n sre -l app=sre-api -o jsonpath="{.items[0].metadata.name}"
```

Then:

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/healthz'); print('healthz=',r.status); print(r.read().decode())"
```

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/readyz'); print('readyz=',r.status); print(r.read().decode())"
```

```powershell
kubectl exec $SrePod -n sre -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/demo'); print('demo=',r.status); print(r.read().decode())"
```

Expected:

```text
healthz = 200
readyz  = 200
demo    = 200
```

---

# 18. Verify the restart timestamp

```powershell
kubectl get deployment sre-api -n sre -o jsonpath="{.spec.template.metadata.annotations.sre\.azure\.com/remediation-restarted-at}"
```

This proves the restart runbook changed the pod template and triggered the new Deployment revision.

---

# 19. How to explain the complete live incident

After the commands, your explanation can be:

> The application exposes Prometheus metrics and Kubernetes health endpoints. I intentionally enabled a controlled failure mode, which caused readiness to return 503 while the application remained running. Managed Prometheus detected the sustained 5xx rate and Azure Monitor generated the alert. The Incident Collector received the webhook, collected pod state, logs, and Kubernetes events, and sent the evidence to the AI analyser. The AI generated a structured RCA, but it did not execute anything. I explicitly approved the restart runbook. The Incident Collector then executed the registered runbook, waited for the Deployment rollout, and verified healthz, readyz, and demo before marking the incident successful.

That is the strongest part of the project.

---

# 20. How to demonstrate the scale runbook

For the interview, I recommend **showing the already successful scale incident rather than rerunning it live**.

Why?

Your HPA is currently active:

```text
2 → 8
CPU target 70%
```

and the scale runbook test was performed with the HPA temporarily removed so that HPA would not immediately reconcile the replica count.

The exact successful result was:

```text
2 replicas
    ↓
requested 3
    ↓
observed 3
    ↓
available 3
    ↓
health verification passed
```

Use the stored incident command:

```powershell
$IncidentId = "18df1613-1cea-4f70-b2f7-599e37f8d0a7"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

---

# 21. How to demonstrate the rollback runbook

Again, **show the successful stored rollback rather than rerunning it during the interview**.

The validated scenario was:

```text
713
 ↓
incident
 ↓
rollback
 ↓
712
 ↓
health verification
```

Use:

```powershell
$IncidentId = "a192c306-e78c-4209-b117-86259804c7d9"

kubectl exec deployment/incident-collector -n sre -- python -c "import urllib.request; incident_id='$IncidentId'; r=urllib.request.urlopen('http://127.0.0.1:8080/incidents/'+incident_id); print(r.read().decode())"
```

Then explain:

> The rollback runbook finds the previous ReplicaSet revision rather than accepting an arbitrary image from the operator or AI. It restores the previous pod template and validates the final image and application health.

That is much safer than changing the current environment just to demonstrate rollback.

---

# 22. Show the current ReplicaSet history

This is useful when discussing rollback:

```powershell
kubectl get rs -n sre -l app=sre-api -o custom-columns="NAME:.metadata.name,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision,DESIRED:.spec.replicas,READY:.status.readyReplicas"
```

You can explain:

> Kubernetes keeps previous ReplicaSets, and my rollback runbook uses those revisions to identify the previous deployment.

---

# 23. Show Helm ownership after remediation

If the interviewer is technically strong, run:

```powershell
kubectl get deployment sre-api -n sre -o json --show-managed-fields | ConvertFrom-Json | Select-Object -ExpandProperty metadata | Select-Object -ExpandProperty managedFields | ForEach-Object { "$($_.manager): " + ($_.fieldsV1 | ConvertTo-Json -Depth 20 -Compress) } | Select-String '"f:image"'
```

Expected:

```text
helm: ... "f:image":{} ...
```

Then explain:

> During rollback, the remediation manager temporarily took ownership of the image field. The next Helm deployment originally hit a Server-Side Apply conflict. I handled that by adding `--force-conflicts`, after which Helm successfully reclaimed ownership.

This is an excellent real-world troubleshooting example.

---

# 24. Best interview sequence

I would personally run the interview in this order:

```text
1. kubectl get deployments
2. kubectl get pods
3. kubectl get hpa
4. /healthz
5. /readyz
6. /demo
7. /metrics
8. GET /runbooks
9. Show Grafana dashboard
10. Show Azure Monitor alert
11. Show completed restart incident
12. Show completed scale incident
13. Show completed rollback incident
14. Show Helm field ownership
```

Then, only when the interviewer wants a **live failure demonstration**:

```text
Enable failure mode
       ↓
Show pods NotReady
       ↓
Wait for alert
       ↓
Show Incident Collector incident
       ↓
Show AI RCA
       ↓
Approve restart
       ↓
Execute restart
       ↓
Show 2/2 healthy
       ↓
healthz / readyz / demo = 200
```

---

# 25. Commands you should memorize

You don't need to memorize every command. These are the important ones to know naturally:

### Cluster state

```powershell
kubectl get deployments -n sre
kubectl get pods -n sre
kubectl get hpa -n sre
```

### Application health

```powershell
kubectl exec <pod> -n sre -- ...
```

for:

```text
/healthz
/readyz
/demo
```

### Runbooks

```powershell
GET /runbooks
```

through the Incident Collector.

### Incident

```powershell
GET /incidents/{incident_id}
```

### Approval

```text
POST /incidents/{incident_id}/approve
```

### Remediation

```text
POST /incidents/{incident_id}/remediate
```

### Deployment

```powershell
kubectl get deployment sre-api -n sre
kubectl rollout status deployment/sre-api -n sre
```

### Rollback investigation

```powershell
kubectl get rs -n sre -l app=sre-api
```

---

## One important recommendation for the interview

**Do not start the interview by deliberately breaking the cluster.**

Start with the healthy environment and show the architecture, Grafana, runbooks, and the already successful incident records. Then perform the live restart test only when the interviewer wants to see the automation actually execute.

That gives you a much cleaner demonstration and avoids spending 5–7 minutes waiting for Azure Monitor while the interviewer watches.
