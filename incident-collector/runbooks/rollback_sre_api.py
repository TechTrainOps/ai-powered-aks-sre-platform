from __future__ import annotations

from typing import Any

from kubernetes.client import ApiClient
from kubernetes.client.exceptions import ApiException

from .base import Runbook


DEPLOYMENT_NAME = "sre-api"


class RollbackSreApiRunbook(Runbook):

    name = "rollback-sre-api"

    description = (
        "Rollback sre-api to the immediately previous "
        "Deployment revision and verify application health."
    )

    risk = "high"

    def validate_parameters(
        self,
        parameters: dict[str, Any],
    ) -> None:

        if parameters:
            raise ValueError(
                "rollback-sre-api does not accept parameters."
            )

    def execute(
        self,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:

        deployment_name = DEPLOYMENT_NAME

        try:
            deployment = (
                self.apps_api
                .read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )
            )

            current_revision_value = (
                deployment.metadata.annotations or {}
            ).get(
                "deployment.kubernetes.io/revision"
            )

            if not current_revision_value:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "error": (
                        "Current Deployment revision could "
                        "not be determined."
                    ),
                }

            try:
                current_revision = int(
                    current_revision_value
                )
            except ValueError:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "error": (
                        "Current Deployment revision is "
                        f"invalid: {current_revision_value}"
                    ),
                }

            replica_sets = (
                self.apps_api
                .list_namespaced_replica_set(
                    namespace=self.namespace,
                    label_selector=(
                        "app=sre-api"
                    ),
                )
            )

            candidate_revisions = []

            for replica_set in replica_sets.items:

                owner_references = (
                    replica_set.metadata.owner_references
                    or []
                )

                controlled_by_current_deployment = any(
                    owner.kind == "Deployment"
                    and owner.name == deployment_name
                    for owner in owner_references
                )

                if not controlled_by_current_deployment:
                    continue

                annotations = (
                    replica_set.metadata.annotations or {}
                )

                revision_value = annotations.get(
                    "deployment.kubernetes.io/revision"
                )

                if not revision_value:
                    continue

                try:
                    revision = int(revision_value)
                except ValueError:
                    continue

                if revision < current_revision:
                    candidate_revisions.append(
                        (
                            revision,
                            replica_set,
                        )
                    )

            if not candidate_revisions:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "error": (
                        "No previous Deployment revision "
                        "was found."
                    ),
                }

            target_revision, previous_replica_set = max(
                candidate_revisions,
                key=lambda item: item[0],
            )

            current_image = None

            if (
                deployment.spec.template
                and deployment.spec.template.spec
                and deployment.spec.template.spec.containers
            ):
                current_image = (
                    deployment
                    .spec
                    .template
                    .spec
                    .containers[0]
                    .image
                )

            target_template = (
                previous_replica_set
                .spec
                .template
                .to_dict()
            )

            target_labels = (
                target_template
                .get("metadata", {})
                .get("labels", {})
            )

            target_labels.pop(
                "pod-template-hash",
                None,
            )

            target_annotations = (
                target_template
                .get("metadata", {})
                .get("annotations", {})
            )

            target_template["metadata"][
                "labels"
            ] = target_labels

            target_template["metadata"][
                "annotations"
            ] = target_annotations

            target_image = None

            target_containers = (
                target_template
                .get("spec", {})
                .get("containers", [])
            )

            if target_containers:
                target_image = target_containers[0].get(
                    "image"
                )

            execution = {
                "status": "started",
                "current_revision": current_revision,
                "target_revision": target_revision,
                "current_image": current_image,
                "target_image": target_image,
                "target_replica_set": (
                    previous_replica_set.metadata.name
                ),
            }

            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body={
                    "spec": {
                        "template": target_template,
                    }
                },
            )

            rollout = self.wait_for_rollout()

            if not rollout.get("success"):
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": execution,
                    "rollout": rollout,
                    "verification": None,
                }

            final_deployment = (
                self.apps_api
                .read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )
            )

            final_revision = (
                (
                    final_deployment
                    .metadata
                    .annotations
                    or {}
                ).get(
                    "deployment.kubernetes.io/revision"
                )
            )

            final_image = None

            if (
                final_deployment.spec.template
                and final_deployment.spec.template.spec
                and final_deployment.spec.template.spec.containers
            ):
                final_image = (
                    final_deployment
                    .spec
                    .template
                    .spec
                    .containers[0]
                    .image
                )

            execution[
                "final_revision"
            ] = final_revision

            execution[
                "final_image"
            ] = final_image

            if final_image != target_image:
                return {
                    "success": False,
                    "runbook": self.name,
                    "deployment": deployment_name,
                    "execution": execution,
                    "rollout": rollout,
                    "verification": None,
                    "reconciliation": {
                        "status": "RollbackTargetMismatch",
                        "target_revision": target_revision,
                        "final_revision": final_revision,
                        "target_image": target_image,
                        "final_image": final_image,
                        "message": (
                            "The Deployment did not end on "
                            "the expected previous revision."
                        ),
                    },
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
                "rollout": rollout,
                "reconciliation": None,
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

        except Exception as exc:
            return {
                "success": False,
                "runbook": self.name,
                "deployment": deployment_name,
                "error": (
                    "Unexpected error during "
                    f"rollback: {exc}"
                ),
            }