from __future__ import annotations

import time
from typing import Any

from kubernetes.client.exceptions import ApiException

from .base import Runbook


DEPLOYMENT_NAME = "sre-api"

MIN_REPLICAS = 1
MAX_REPLICAS = 5

REPLICA_RECONCILIATION_TIMEOUT_SECONDS = 30
REPLICA_RECONCILIATION_POLL_SECONDS = 3

REPLICA_AVAILABILITY_TIMEOUT_SECONDS = 120
REPLICA_AVAILABILITY_POLL_SECONDS = 3


class ScaleSreApiRunbook(Runbook):

    name = "scale-sre-api"

    description = (
        "Scale sre-api between 1 and 5 replicas, "
        "verify the requested replica count, "
        "verify replica availability, "
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

            actual_replicas = current_replicas

            reconciliation_deadline = (
                time.time()
                + REPLICA_RECONCILIATION_TIMEOUT_SECONDS
            )

            while time.time() < reconciliation_deadline:
                deployment = (
                    self.apps_api
                    .read_namespaced_deployment(
                        name=deployment_name,
                        namespace=self.namespace,
                    )
                )

                actual_replicas = (
                    deployment.spec.replicas or 0
                )

                if actual_replicas == replicas:
                    break

                time.sleep(
                    REPLICA_RECONCILIATION_POLL_SECONDS
                )

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
                    "rollout": None,
                    "verification": None,
                }

            availability_deadline = (
                time.time()
                + REPLICA_AVAILABILITY_TIMEOUT_SECONDS
            )

            available_replicas = 0
            unavailable_replicas = 0

            while time.time() < availability_deadline:
                deployment = (
                    self.apps_api
                    .read_namespaced_deployment(
                        name=deployment_name,
                        namespace=self.namespace,
                    )
                )

                actual_replicas = (
                    deployment.spec.replicas or 0
                )

                available_replicas = (
                    deployment.status.available_replicas
                    or 0
                )

                unavailable_replicas = (
                    deployment.status.unavailable_replicas
                    or 0
                )

                if actual_replicas != replicas:
                    execution[
                        "observed_replicas"
                    ] = actual_replicas

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
                                "Another Kubernetes controller "
                                "may have reconciled the replica "
                                "count."
                            ),
                        },
                        "rollout": None,
                        "verification": None,
                    }

                if (
                    available_replicas >= replicas
                    and unavailable_replicas == 0
                ):
                    break

                time.sleep(
                    REPLICA_AVAILABILITY_POLL_SECONDS
                )

            rollout = {
                "success": (
                    actual_replicas == replicas
                    and available_replicas >= replicas
                    and unavailable_replicas == 0
                ),
                "requested_replicas": replicas,
                "observed_replicas": actual_replicas,
                "available_replicas": available_replicas,
                "unavailable_replicas": unavailable_replicas,
            }

            execution[
                "observed_replicas"
            ] = actual_replicas

            if not rollout["success"]:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": execution,
                    "reconciliation": None,
                    "rollout": rollout,
                    "verification": None,
                }

            verification = self.verify_sre_api()

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