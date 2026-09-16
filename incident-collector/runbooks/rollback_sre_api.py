from __future__ import annotations

import copy
from typing import Any

from kubernetes.client.exceptions import ApiException

from .base import Runbook


DEPLOYMENT_NAME = "sre-api"


class RollbackSreApiRunbook(Runbook):

    name = "rollback-sre-api"

    description = (
        "Rollback sre-api to the immediately "
        "previous Deployment revision."
    )

    risk = "high"

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

    @staticmethod
    def _revision(
        replica_set: Any,
    ) -> int:

        annotations = (
            replica_set.metadata.annotations
            or {}
        )

        value = annotations.get(
            "deployment.kubernetes.io/revision"
        )

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _deployment_revision(
        deployment: Any,
    ) -> int:

        annotations = (
            deployment.metadata.annotations
            or {}
        )

        value = annotations.get(
            "deployment.kubernetes.io/revision"
        )

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0

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

            current_revision = (
                self._deployment_revision(
                    deployment
                )
            )

            replica_sets = (
                self.apps_api
                .list_namespaced_replica_set(
                    namespace=self.namespace,
                )
            )

            owned_replica_sets = []

            deployment_uid = (
                deployment.metadata.uid
            )

            for replica_set in (
                replica_sets.items
            ):

                owners = (
                    replica_set.metadata.owner_references
                    or []
                )

                owned = any(
                    owner.kind == "Deployment"
                    and owner.name
                    == deployment_name
                    and owner.uid
                    == deployment_uid
                    for owner in owners
                )

                if owned:
                    owned_replica_sets.append(
                        replica_set
                    )

            candidates = [
                rs
                for rs in owned_replica_sets
                if self._revision(rs)
                < current_revision
            ]

            candidates.sort(
                key=self._revision,
                reverse=True,
            )

            if not candidates:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "error": (
                        "No previous ReplicaSet revision "
                        "was found for rollback."
                    ),
                }

            previous = candidates[0]

            previous_revision = self._revision(
                previous
            )

            if (
                previous.spec is None
                or previous.spec.template is None
            ):
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "error": (
                        "Previous ReplicaSet does not "
                        "contain a valid pod template."
                    ),
                }

            template = copy.deepcopy(
                previous.spec.template
            )

            template_dict = template.to_dict()

            metadata = template_dict.setdefault(
                "metadata",
                {},
            )

            labels = dict(
                metadata.get(
                    "labels",
                    {},
                )
                or {}
            )

            annotations = dict(
                metadata.get(
                    "annotations",
                    {},
                )
                or {}
            )

            labels.pop(
                "pod-template-hash",
                None,
            )

            annotations.pop(
                "deployment.kubernetes.io/revision",
                None,
            )

            metadata["labels"] = labels
            metadata["annotations"] = annotations

            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body={
                    "spec": {
                        "template": template_dict,
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
                        "current_revision": (
                            current_revision
                        ),
                        "target_revision": (
                            previous_revision
                        ),
                        "target_replica_set": (
                            previous.metadata.name
                        ),
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
                    "current_revision": (
                        current_revision
                    ),
                    "target_revision": (
                        previous_revision
                    ),
                    "target_replica_set": (
                        previous.metadata.name
                    ),
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
                    "Unable to rollback sre-api deployment: "
                    f"HTTP {exc.status}: {exc.reason}"
                ),
            }
