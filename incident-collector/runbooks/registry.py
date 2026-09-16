from __future__ import annotations

from typing import Any

from .restart_sre_api import RestartSreApiRunbook
from .rollback_sre_api import RollbackSreApiRunbook
from .scale_sre_api import ScaleSreApiRunbook


RUNBOOK_METADATA = {
    "restart-sre-api": {
        "description": (
            "Perform a rolling restart of sre-api "
            "and verify application health."
        ),
        "risk": "medium",
        "requires_approval": True,
    },
    "scale-sre-api": {
        "description": (
            "Scale sre-api between 1 and 5 replicas "
            "and verify application health."
        ),
        "risk": "medium",
        "requires_approval": True,
    },
    "rollback-sre-api": {
        "description": (
            "Rollback sre-api to the immediately "
            "previous Deployment revision."
        ),
        "risk": "high",
        "requires_approval": True,
    },
}


def get_runbook(
    name: str,
    core_api: Any,
    apps_api: Any,
    namespace: str,
    utc_now,
    wait_for_rollout,
    verify_sre_api,
):
    runbook_types = {
        "restart-sre-api": RestartSreApiRunbook,
        "scale-sre-api": ScaleSreApiRunbook,
        "rollback-sre-api": RollbackSreApiRunbook,
    }

    runbook_type = runbook_types.get(name)

    if runbook_type is None:
        raise ValueError(
            f"Unknown runbook: {name}"
        )

    return runbook_type(
        core_api=core_api,
        apps_api=apps_api,
        namespace=namespace,
        utc_now=utc_now,
        wait_for_rollout=wait_for_rollout,
        verify_sre_api=verify_sre_api,
    )


def list_runbooks() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            **metadata,
        }
        for name, metadata
        in RUNBOOK_METADATA.items()
    ]
