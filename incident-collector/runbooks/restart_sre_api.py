from __future__ import annotations

from typing import Any

from kubernetes.client.exceptions import ApiException

from .base import Runbook


DEPLOYMENT_NAME = "sre-api"


class RestartSreApiRunbook(Runbook):

    name = "restart-sre-api"

    description = (
        "Perform a rolling restart of sre-api "
        "and verify application health."
    )

    risk = "medium"

    def validate_parameters(
        self,
        parameters: dict[str, Any],
    ) -> None:

        allowed = {
            "deployment",
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

    def execute(
        self,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:

        deployment_name = parameters.get(
            "deployment",
            DEPLOYMENT_NAME,
        )

        try:
            deployment = (
                self.apps_api
                .read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )
            )

            existing_annotations = (
                deployment.spec.template.metadata.annotations
                if deployment.spec.template.metadata
                and deployment.spec.template.metadata.annotations
                else {}
            )

            annotations = dict(
                existing_annotations
            )

            restarted_at = self.utc_now()

            annotations[
                "sre.azure.com/remediation-restarted-at"
            ] = restarted_at

            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body={
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": annotations,
                            }
                        }
                    }
                },
            )

            rollout = self.wait_for_rollout()

            if not rollout.get("success"):
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": {
                        "status": "started",
                        "restarted_at": restarted_at,
                    },
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
                "execution": {
                    "status": "started",
                    "restarted_at": restarted_at,
                },
                "rollout": rollout,
                "verification": verification,
            }

        except ApiException as exc:
            return {
                "success": False,
                "runbook": self.name,
                "deployment": deployment_name,
                "error": (
                    "Unable to restart sre-api deployment: "
                    f"HTTP {exc.status}: {exc.reason}"
                ),
            }
