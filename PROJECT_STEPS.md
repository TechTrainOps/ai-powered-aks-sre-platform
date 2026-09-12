# Project build sequence and learning checklist

## Phase 1: Foundation

1. Create Azure subscription access.
2. Install CLI tooling.
3. Initialize Git repository.
4. Create Terraform provider configuration.
5. Provision resource group.
6. Provision VNet and AKS subnet.
7. Provision ACR.
8. Provision Log Analytics.
9. Provision Azure Monitor workspace.
10. Provision Azure Managed Grafana.
11. Provision AKS.
12. Enable OIDC and Workload Identity.
13. Create user-assigned identities.
14. Create federated credentials.
15. Assign ACR pull role.
16. Assign OpenAI user role.
17. Assign Log Analytics reader role.

## Phase 2: Application

1. Write FastAPI service.
2. Add `/healthz`.
3. Add `/readyz`.
4. Add `/metrics`.
5. Add Prometheus request and latency metrics.
6. Add controlled failure mode for demo testing.
7. Add unit tests.
8. Containerize with a non-root user.

## Phase 3: Kubernetes

1. Create namespace.
2. Create service accounts.
3. Add Workload Identity annotations.
4. Create deployments.
5. Add CPU/memory requests.
6. Add probes.
7. Add Service.
8. Add HPA.
9. Add PDB.
10. Add RBAC for collector.
11. Add Prometheus scrape annotations.
12. Validate with Helm lint.

## Phase 4: Observability

1. Enable Container Insights.
2. Enable managed Prometheus.
3. Connect Azure Monitor workspace to Grafana.
4. Create dashboards.
5. Validate `/metrics`.
6. Validate logs in Log Analytics.
7. Create 5xx alert.
8. Create restart alert.
9. Create CPU alert.

## Phase 5: Incident intelligence

1. Receive Azure Monitor alert.
2. Generate incident ID.
3. Query recent logs.
4. Collect Kubernetes warning events.
5. Query Prometheus-compatible metrics.
6. Normalize evidence.
7. Send evidence to Azure OpenAI.
8. Parse structured response.
9. Validate required fields.
10. Store pending incident.
11. Ask human for approval.
12. Store approval identity/comment.
13. Execute approved runbook manually.
14. Verify recovery.
15. Close incident.

## Phase 6: CI/CD

1. Terraform fmt and validate.
2. Run Python tests.
3. Helm lint.
4. Build containers.
5. Scan images.
6. Push to ACR.
7. Deploy with Helm.
8. Wait for rollout.
9. Run smoke test.
10. Protect infrastructure apply with environment approval.

## Phase 7: Failure drills

### Drill 1: Application 500s

Enable failure mode -> send traffic -> alert -> collect evidence -> AI RCA -> human approval -> disable failure mode -> verify recovery.

### Drill 2: Bad readiness probe

Change readiness path -> deploy -> observe NotReady pods -> inspect pod events -> fix Helm value -> redeploy.

### Drill 3: ImagePullBackOff

Push a deliberately wrong image tag -> deploy -> inspect events -> correct tag -> redeploy.

### Drill 4: HPA unknown metrics

Remove CPU requests in a branch -> apply -> inspect HPA -> restore requests -> verify scaling.

### Drill 5: Workload Identity failure

Break the federated credential subject -> inspect pod environment and identity errors -> restore the exact subject -> wait for propagation -> retest Azure OpenAI call.

### Drill 6: Log Analytics permission failure

Remove collector read role -> trigger alert -> inspect collector logs -> restore role -> retest.
