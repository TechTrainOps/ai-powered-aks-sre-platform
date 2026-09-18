from __future__ import annotations

from typing import Any

from kubernetes.client.exceptions import ApiException

from .base import Runbook


DEPLOYMENT_NAME = "sre-api"
MIN_REPLICAS = 1
MAX_REPLICAS = 5


class ScaleSreApiRunbook(Runbook):

    name = "scale-sre-api"

    description = (
        "Scale sre-api between 1 and 5 replicas, "
        "verify the requested replica count, "
        "and verify application health."
    )

    risk = "medium"

    def validate_parameters(
        self,
        parameters: dict[str, Any],
    ) -> None:

        allowed = {
            "deployment",
            "replicas",
        }

        unknown = set(parameters) - allowed

        if unknown:
            raise ValueError(
                "Unsupported parameters: "
                f"{sorted(unknown)}"
            )

        deployment = parameters.get(
            "deployment",
            DEPLOYMENT_NAME,
        )

        if deployment != DEPLOYMENT_NAME:
            raise ValueError(
                "Only sre-api is allowed for "
                "this runbook."
            )

        if "replicas" not in parameters:
            raise ValueError(
                "replicas parameter is required."
            )

        replicas = parameters["replicas"]

        if isinstance(
            replicas,
            bool,
        ) or not isinstance(
            replicas,
            int,
        ):
            raise ValueError(
                "replicas must be an integer."
            )

        if replicas < MIN_REPLICAS:
            raise ValueError(
                f"replicas cannot be less than "
                f"{MIN_REPLICAS}."
            )

        if replicas > MAX_REPLICAS:
            raise ValueError(
                f"replicas cannot be greater than "
                f"{MAX_REPLICAS}."
            )

    def execute(
        self,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:

        deployment_name = parameters.get(
            "deployment",
            DEPLOYMENT_NAME,
        )

        replicas = parameters["replicas"]

        try:
            deployment = (
                self.apps_api
                .read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )
            )

            current_replicas = (
                deployment.spec.replicas or 0
            )

            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body={
                    "spec": {
                        "replicas": replicas,
                    }
                },
            )

            rollout = self.wait_for_rollout()

            final_deployment = (
                self.apps_api
                .read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )
            )

            actual_replicas = (
                final_deployment.spec.replicas or 0
            )

            verification = self.verify_sre_api()

            execution = {
                "status": "started",
                "previous_replicas": current_replicas,
                "requested_replicas": replicas,
                "observed_replicas": actual_replicas,
            }

            if actual_replicas != replicas:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": execution,
                    "reconciliation": {
                        "status": "ReplicaCountMismatch",
                        "requested_replicas": replicas,
                        "observed_replicas": actual_replicas,
                        "message": (
                            "The requested replica count was "
                            "not maintained by the Deployment. "
                            "Another Kubernetes controller may "
                            "have reconciled the replica count."
                        ),
                    },
                    "rollout": rollout,
                    "verification": verification,
                }

            if not rollout.get("success"):
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": execution,
                    "reconciliation": None,
                    "rollout": rollout,
                    "verification": verification,
                }

            return {
                "success": verification.get(
                    "success",
                    False,
                ),
                "runbook": self.name,
                "deployment": deployment_name,
                "execution": execution,
                "reconciliation": None,
                "rollout": rollout,
                "verification": verification,
            }

        except ApiException as exc:
            return {
                "success": False,
                "runbook": self.name,
                "deployment": deployment_name,
                "error": (
                    "Unable to scale sre-api deployment: "
                    f"HTTP {exc.status}: {exc.reason}"
                ),
            }