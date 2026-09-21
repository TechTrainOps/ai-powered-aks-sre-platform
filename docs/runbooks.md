````markdown
# Remediation Runbooks

## 1. Overview

The **AI-Powered AKS SRE & Incident Automation Platform** uses controlled Kubernetes remediation runbooks to perform approved recovery actions after an incident is detected and analysed.

The current runbook set is:

```text
restart-sre-api
scale-sre-api
rollback-sre-api
````

The remediation design follows:

```text
Incident
   |
   v
AI-assisted RCA
   |
   v
Human Approval
   |
   v
Approved Runbook
   |
   v
Parameter Validation
   |
   v
Kubernetes Change
   |
   v
Rollout / Reconciliation
   |
   v
Application Health Verification
   |
   v
Structured Result
```

The AI analyser does not directly execute these runbooks.

---

# 2. Runbook Design

Runbooks are implemented as Python classes using a common abstract interface.

The runbook package is organized as:

```text
incident-collector/
|
├── main.py
├── requirements.txt
├── Dockerfile
|
└── runbooks/
    ├── __init__.py
    ├── base.py
    ├── registry.py
    ├── restart_sre_api.py
    ├── scale_sre_api.py
    └── rollback_sre_api.py
```

The common abstraction is:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Runbook(ABC):
    name: str
    description: str
    risk: str
    requires_approval: bool = True

    def __init__(
        self,
        core_api: Any,
        apps_api: Any,
        namespace: str,
        utc_now,
        wait_for_rollout,
        verify_sre_api,
    ):
        self.core_api = core_api
        self.apps_api = apps_api
        self.namespace = namespace
        self.utc_now = utc_now
        self.wait_for_rollout = wait_for_rollout
        self.verify_sre_api = verify_sre_api

    @abstractmethod
    def validate_parameters(
        self,
        parameters: dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
```

The common interface provides each runbook with:

```text
Kubernetes Core API client
Kubernetes Apps API client
Target namespace
UTC timestamp function
Rollout verification function
Application health verification function
```

---

# 3. Runbook Registry

The Incident Collector maintains a registry of available runbooks.

The currently registered runbooks are:

```text
restart-sre-api
scale-sre-api
rollback-sre-api
```

The registry allows the approval workflow to reference a known runbook rather than accepting arbitrary executable actions.

The Incident Collector exposes:

```text
GET /runbooks
```

to list the registered runbooks.

---

# 4. Approval Model

All remediation runbooks require approval.

The approval request contains the selected runbook and its parameters.

Example:

```json
{
  "runbook": "restart-sre-api",
  "parameters": {},
  "approved_by": "operator"
}
```

After approval, the incident stores:

```text
approval.status
approval.approved_by
approval.approved_at
approval.runbook
approval.parameters
```

The remediation API executes the already approved runbook.

It does not accept a new arbitrary runbook during remediation.

The flow is therefore:

```text
AI Analysis
     |
     v
Recommended Action
     |
     v
Human Approval
     |
     v
Approved Runbook
     |
     v
Execution
```

---

# 5. Restart Runbook

## 5.1 Name

```text
restart-sre-api
```

## 5.2 Risk

```text
high
```

## 5.3 Description

```text
Restart the sre-api deployment and verify application health.
```

The restart runbook performs a controlled Deployment rollout without changing the application image or replica count.

---

# 6. Restart Runbook Flow

```text
Approved Incident
       |
       v
Validate parameters
       |
       v
Read sre-api Deployment
       |
       v
Patch pod template annotation
       |
       v
Kubernetes creates new ReplicaSet
       |
       v
New sre-api pods
       |
       v
Wait for rollout
       |
       v
Verify application health
       |
       v
Return structured result
```

---

# 7. Restart Parameters

The restart runbook does not require parameters.

Valid input:

```json
{}
```

Any non-empty parameter object is rejected.

This keeps the restart operation intentionally deterministic.

---

# 8. Restart Mechanism

The runbook updates the Deployment pod-template annotation:

```text
sre.azure.com/remediation-restarted-at
```

The timestamp is generated during execution.

Changing the pod template causes Kubernetes to create a new ReplicaSet and roll the application pods.

Conceptually:

```text
Existing Deployment
       |
       v
Pod template annotation changed
       |
       v
Deployment revision changes
       |
       v
New ReplicaSet
       |
       v
New pods
```

The container image remains unchanged.

---

# 9. Restart Rollout Verification

After patching the Deployment, the runbook verifies the rollout.

The expected state is:

```text
desired_replicas   = 2
updated_replicas   = 2
available_replicas = 2
unavailable_replicas = 0
```

The rollout must complete successfully before application verification is performed.

---

# 10. Restart Application Verification

The runbook verifies:

```text
/healthz
/readyz
/demo
```

Expected results:

```text
healthz = HTTP 200
readyz  = HTTP 200
demo    = HTTP 200
```

The remediation is considered successful only when the rollout and application verification succeed.

---

# 11. Restart Result Structure

A successful restart returns a structured result similar to:

```json
{
  "success": true,
  "runbook": "restart-sre-api",
  "deployment": "sre-api",
  "execution": {
    "status": "started",
    "restarted_at": "..."
  },
  "rollout": {
    "success": true,
    "deployment": "sre-api",
    "desired_replicas": 2,
    "updated_replicas": 2,
    "available_replicas": 2,
    "unavailable_replicas": 0,
    "observed_generation": 43,
    "generation": 43
  },
  "verification": {
    "success": true,
    "endpoints": {
      "healthz": {
        "status_code": 200
      },
      "readyz": {
        "status_code": 200
      },
      "demo": {
        "status_code": 200
      }
    }
  }
}
```

---

# 12. Scale Runbook

## 12.1 Name

```text
scale-sre-api
```

## 12.2 Risk

```text
medium
```

## 12.3 Description

```text
Scale sre-api between 1 and 5 replicas, verify the requested replica count, verify replica availability, and verify application health.
```

The scale runbook changes only the Deployment replica count.

---

# 13. Scale Parameters

The runbook accepts:

```json
{
  "replicas": 3
}
```

The supported remediation range is:

```text
Minimum: 1
Maximum: 5
```

Valid examples:

```json
{
  "replicas": 1
}
```

```json
{
  "replicas": 3
}
```

```json
{
  "replicas": 5
}
```

Invalid examples include:

```json
{
  "replicas": 0
}
```

```json
{
  "replicas": 6
}
```

```json
{
  "replicas": "3"
}
```

The parameters are validated before the Kubernetes Deployment is modified.

---

# 14. Scale Reconciliation

The scale runbook intentionally separates replica reconciliation from replica availability.

The execution flow is:

```text
Validate replicas
       |
       v
Patch Deployment.spec.replicas
       |
       v
Poll Deployment.spec.replicas
       |
       v
Requested replica count reached?
       |
       +---- No ----> ReplicaCountMismatch
       |
       +---- Yes
              |
              v
       Wait for availability
              |
              v
       All replicas available?
              |
              +---- No ----> Availability/Timeout failure
              |
              +---- Yes
                     |
                     v
             Application verification
```

This prevents the runbook from reporting success just because the Kubernetes PATCH request was accepted.

---

# 15. Scale Reconciliation Timeouts

The scale implementation uses:

```text
Replica reconciliation timeout:
30 seconds

Replica reconciliation polling:
3 seconds
```

Once the requested replica count is reached, availability is checked using:

```text
Replica availability timeout:
120 seconds

Replica availability polling:
3 seconds
```

---

# 16. Scale Replica Availability Verification

After Kubernetes reports the requested replica count, the runbook checks:

```text
availableReplicas
unavailableReplicas
```

A successful scale operation requires:

```text
availableReplicas == requested replicas
```

and:

```text
unavailableReplicas == 0
```

---

# 17. Scale Application Verification

Once the requested replicas are available, the runbook verifies:

```text
/healthz
/readyz
/demo
```

Expected:

```text
healthz = HTTP 200
readyz  = HTTP 200
demo    = HTTP 200
```

---

# 18. Scale Result Structure

A successful scale operation returns structured information similar to:

```json
{
  "success": true,
  "runbook": "scale-sre-api",
  "deployment": "sre-api",
  "previous_replicas": 2,
  "requested_replicas": 3,
  "observed_replicas": 3,
  "available_replicas": 3,
  "unavailable_replicas": 0,
  "reconciliation": {
    "status": "ReplicaCountReached"
  },
  "verification": {
    "success": true,
    "endpoints": {
      "healthz": {
        "status_code": 200
      },
      "readyz": {
        "status_code": 200
      },
      "demo": {
        "status_code": 200
      }
    }
  }
}
```

When the requested count is not reached within the reconciliation timeout, the runbook returns a failure rather than continuing as if the scale operation succeeded.

Example failure state:

```text
success = false
reconciliation.status = ReplicaCountMismatch
```

---

# 19. Rollback Runbook

## 19.1 Name

```text
rollback-sre-api
```

## 19.2 Risk

```text
high
```

## 19.3 Description

```text
Rollback sre-api to the immediately previous Deployment revision and verify application health.
```

The rollback runbook restores the previous Deployment revision based on Kubernetes Deployment history.

---

# 20. Rollback Parameters

The rollback runbook does not accept parameters.

Valid input:

```json
{}
```

An attempt to provide parameters is rejected.

This prevents the approval request from directly specifying an arbitrary image or revision.

---

# 21. Rollback Revision Discovery

The rollback process begins by reading the current Deployment.

The runbook obtains:

```text
Current Deployment
Current revision
Current image
```

It then lists ReplicaSets associated with:

```text
sre-api
```

The runbook filters ReplicaSets based on their Deployment ownership and extracts their revision annotations.

Conceptually:

```text
Current Deployment
        |
        v
Current revision = N
        |
        v
List sre-api ReplicaSets
        |
        v
Find revisions < N
        |
        v
Select highest revision < N
        |
        v
Previous revision = N-1
```

The target is therefore the immediately previous known Deployment revision.

---

# 22. Rollback Pod Template

After identifying the previous ReplicaSet, the runbook obtains its pod template.

The previous pod template is serialized using the Kubernetes API client's serialization mechanism.

This is important because Kubernetes API objects cannot safely be converted to a Deployment patch by directly using Python object `to_dict()` output.

The rollback implementation uses:

```python
from kubernetes.client import ApiClient

target_template = ApiClient().sanitize_for_serialization(
    previous_replica_set.spec.template
)
```

The serialized template is then used to construct the Deployment patch.

---

# 23. Rollback Target Image

The target image is obtained from the previous ReplicaSet.

Example:

```text
Current image:
acrakssreqtyn6.azurecr.io/sre-api:713

Previous image:
acrakssreqtyn6.azurecr.io/sre-api:712
```

The rollback runbook verifies that the final Deployment image matches the identified rollback target.

If the final image does not match the target, the runbook reports:

```text
RollbackTargetMismatch
```

rather than reporting success.

---

# 24. Rollback Execution Flow

```text
Approved Incident
       |
       v
Validate parameters
       |
       v
Read current Deployment
       |
       v
Read current revision
       |
       v
List ReplicaSets
       |
       v
Identify previous revision
       |
       v
Read previous pod template
       |
       v
Patch Deployment
       |
       v
Wait for rollout
       |
       v
Read final Deployment
       |
       v
Verify final image
       |
       v
Verify application health
       |
       v
Return structured result
```

---

# 25. Rollback Safety

The rollback runbook does not accept:

```text
Arbitrary image
Arbitrary revision
Arbitrary container name
```

from the approval request.

The rollback target is derived from Kubernetes ReplicaSet history.

This provides a more controlled rollback mechanism than allowing an operator or AI response to provide an arbitrary image value.

---

# 26. Rollback Rollout Verification

The runbook verifies:

```text
desired_replicas
updated_replicas
available_replicas
unavailable_replicas
observed_generation
generation
```

A successful rollout requires the expected replicas to be updated and available.

---

# 27. Rollback Application Verification

After the target image is confirmed, the runbook verifies:

```text
/healthz
/readyz
/demo
```

Expected:

```text
healthz = HTTP 200
readyz  = HTTP 200
demo    = HTTP 200
```

---

# 28. Rollback Result Structure

A successful rollback returns structured information similar to:

```json
{
  "success": true,
  "runbook": "rollback-sre-api",
  "current_revision": 32,
  "target_revision": 31,
  "current_image": "acrakssreqtyn6.azurecr.io/sre-api:713",
  "target_image": "acrakssreqtyn6.azurecr.io/sre-api:712",
  "target_replica_set": "sre-api-7d74bdfb4c",
  "final_revision": 33,
  "final_image": "acrakssreqtyn6.azurecr.io/sre-api:712",
  "rollout": {
    "success": true,
    "desired_replicas": 2,
    "updated_replicas": 2,
    "available_replicas": 2,
    "unavailable_replicas": 0
  },
  "verification": {
    "success": true,
    "healthz": 200,
    "readyz": 200,
    "demo": 200
  }
}
```

---

# 29. Runbook Registry Model

The runbook registry provides a fixed set of executable remediation actions.

Conceptually:

```text
Runbook Registry
       |
       +---- restart-sre-api
       |
       +---- scale-sre-api
       |
       +---- rollback-sre-api
```

The incident approval references one of these registered names.

This provides a controlled execution boundary between incident analysis and Kubernetes modification.

---

# 30. Common Runbook Execution Lifecycle

All runbooks follow the same high-level lifecycle:

```text
1. Receive approved incident
        |
        v
2. Load approved runbook
        |
        v
3. Validate parameters
        |
        v
4. Execute Kubernetes operation
        |
        v
5. Verify operation result
        |
        v
6. Verify application health
        |
        v
7. Return structured result
        |
        v
8. Persist result to incident
```

---

# 31. Remediation API Flow

The Incident Collector exposes:

```text
POST /incidents/{incident_id}/remediate
```

The remediation endpoint:

```text
Loads incident
     |
     v
Checks approval state
     |
     v
Reads approved runbook
     |
     v
Reads approved parameters
     |
     v
Resolves runbook from registry
     |
     v
Executes runbook
     |
     v
Updates incident remediation state
```

The endpoint does not accept a new runbook definition.

---

# 32. Remediation Status

The incident remediation object contains:

```json
{
  "status": "NotStarted",
  "runbook": null,
  "started_at": null,
  "completed_at": null,
  "result": null
}
```

During execution:

```text
NotStarted
    |
    v
Running
    |
    v
Succeeded
```

or:

```text
NotStarted
    |
    v
Running
    |
    v
Failed
```

The final remediation result contains the runbook-specific execution details.

---

# 33. Failure Handling

Runbooks are designed to return explicit failure results.

Examples include:

```text
Invalid parameters
Deployment not found
Replica count mismatch
Replica availability timeout
Rollout timeout
Previous ReplicaSet unavailable
Rollback target mismatch
Kubernetes API error
Application verification failure
```

A failed Kubernetes API request is not treated as successful remediation.

A successful API PATCH also does not automatically imply application recovery.

The runbook must verify the resulting state.

---

# 34. Kubernetes RBAC Requirements

The Incident Collector uses a dedicated ServiceAccount:

```text
incident-collector
```

The namespace-scoped Role provides:

```text
Core API:
    pods
    pods/log
    events

    get
    list
    watch
```

For Deployments:

```text
apps
    deployments

    get
    patch
```

For rollback:

```text
apps
    replicasets

    get
    list
```

The ReplicaSet permissions are required to identify the previous Deployment revision.

---

# 35. Runbook Security Model

The remediation architecture separates analysis from execution:

```text
Azure Monitor Alert
        |
        v
Incident Collector
        |
        v
Evidence Collection
        |
        v
AI-assisted RCA
        |
        v
Human Approval
        |
        v
Registered Runbook
        |
        v
Restricted Kubernetes RBAC
        |
        v
Remediation
```

The AI analyser does not receive unrestricted Kubernetes permissions.

The Incident Collector uses a dedicated ServiceAccount with only the permissions required for the implemented runbooks and evidence collection.

---

# 36. Restart Test Validation

The restart runbook was validated using a controlled application failure.

The test flow was:

```text
sre-api running normally
        |
        v
Failure mode enabled
        |
        v
Both pods become NotReady
        |
        v
Alert generated
        |
        v
Incident created
        |
        v
AI-assisted RCA
        |
        v
Human approval
        |
        v
restart-sre-api
        |
        v
New Deployment revision
        |
        v
2/2 replicas available
        |
        v
Health verification
```

The final restart test used:

```text
Image:
acrakssreqtyn6.azurecr.io/sre-api:715
```

The Deployment moved from:

```text
Revision 34
```

to:

```text
Revision 35
```

The remediation completed successfully.

Final verification:

```text
healthz = 200
readyz  = 200
demo    = 200
```

---

# 37. Scale Test Validation

The scale runbook was validated using:

```text
Previous replicas: 2
Requested replicas: 3
Observed replicas: 3
Available replicas: 3
Unavailable replicas: 0
```

The remediation completed successfully.

Application verification returned:

```text
healthz = 200
readyz  = 200
demo    = 200
```

The HPA configuration was subsequently restored to:

```text
Minimum replicas: 2
Maximum replicas: 8
CPU target: 70%
```

---

# 38. Rollback Test Validation

The rollback runbook was validated using:

```text
Current revision: 32
Target revision: 31

Current image:
acrakssreqtyn6.azurecr.io/sre-api:713

Target image:
acrakssreqtyn6.azurecr.io/sre-api:712
```

The rollback completed successfully.

Final state:

```text
Final revision: 33
Final image: acrakssreqtyn6.azurecr.io/sre-api:712
Desired replicas: 2
Updated replicas: 2
Available replicas: 2
Unavailable replicas: 0
```

Application verification returned:

```text
healthz = 200
readyz  = 200
demo    = 200
```

---

# 39. Helm Interaction After Rollback

The rollback runbook can temporarily modify the `sre-api` image field that is normally managed by Helm.

During testing, this resulted in a Kubernetes Server-Side Apply field ownership conflict during a later Helm deployment:

```text
conflict with "OpenAPI-Generator"

.spec.template.spec.containers[name="sre-api"].image
```

The Helm deployment was configured with:

```text
--force-conflicts
```

The subsequent CI/CD deployment successfully deployed the newer application image and Helm regained ownership of the image field.

The validated lifecycle is:

```text
Helm
  |
  v
Normal application deployment
  |
  v
Incident
  |
  v
Rollback runbook
  |
  v
Previous image
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
New application image
```

This allows remediation and normal Helm-based deployment to coexist.

---

# 40. Design Principles

## Human Approval

Every remediation action requires explicit approval.

## Fixed Runbook Set

Only registered runbooks can be executed.

## Parameter Validation

Each runbook validates its parameters before performing a Kubernetes change.

## Least Privilege

The Incident Collector uses namespace-scoped Kubernetes RBAC.

## Deterministic Execution

Runbooks contain predefined logic rather than executing arbitrary AI-generated commands.

## Post-Action Verification

Every runbook verifies the result of its Kubernetes operation.

## Application Verification

The `sre-api` health endpoints are checked after remediation.

## Structured Results

Runbooks return structured execution information that is stored in the incident record.

## Safe Rollback

Rollback derives its target from the previous Kubernetes Deployment revision instead of accepting an arbitrary image.

---

# 41. Runbook Comparison

| Runbook            | Purpose                              | Parameters     | Risk   | Main Verification                     |
| ------------------ | ------------------------------------ | -------------- | ------ | ------------------------------------- |
| `restart-sre-api`  | Restart application pods             | None           | High   | Rollout + health                      |
| `scale-sre-api`    | Change replica count                 | `replicas` 1–5 | Medium | Replica count + availability + health |
| `rollback-sre-api` | Restore previous Deployment revision | None           | High   | Revision + image + rollout + health   |

---

# 42. Final Runbook Architecture

```text
                    +----------------------+
                    |    Approved Incident |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |   Runbook Registry   |
                    +----------+-----------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
      restart-sre-api   scale-sre-api   rollback-sre-api
              |                |                |
              v                v                v
      Validate Params    Validate Params   Validate Params
              |                |                |
              v                v                v
      Patch Deployment   Patch Replicas   Find Previous Revision
              |                |                |
              v                v                v
       New ReplicaSet   Reconciliation     Patch Deployment
              |                |                |
              +----------------+----------------+
                               |
                               v
                    +----------------------+
                    | Rollout / State      |
                    | Verification         |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Application Health   |
                    | Verification         |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Structured Result    |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Incident Record      |
                    | Azure Blob Storage   |
                    +----------------------+
```

---

# 43. Final Runbook Summary

The platform currently supports three approval-gated remediation actions:

```text
restart-sre-api
        |
        v
Controlled Deployment restart
        |
        v
Rollout verification
        |
        v
Health verification
```

```text
scale-sre-api
        |
        v
Validated replica count change
        |
        v
Replica reconciliation
        |
        v
Availability verification
        |
        v
Health verification
```

```text
rollback-sre-api
        |
        v
Previous Deployment revision discovery
        |
        v
Previous pod template restoration
        |
        v
Target image verification
        |
        v
Rollout verification
        |
        v
Health verification
```

All three runbooks follow the same core principle:

```text
Approved Action
      |
      v
Controlled Kubernetes Change
      |
      v
Verify the Result
      |
      v
Record the Outcome
```

The runbook layer therefore provides a deterministic and auditable remediation mechanism between the AI-assisted analysis layer and the Kubernetes platform.

```
```
