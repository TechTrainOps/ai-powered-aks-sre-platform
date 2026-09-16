from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Runbook(ABC):
    """
    Base class for all SRE remediation runbooks.
    """

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
