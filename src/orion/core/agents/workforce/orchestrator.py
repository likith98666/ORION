"""Concurrent, thread-safe workforce task orchestrator for V4."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from orion.core.agents.workforce.contracts import WorkforceContractRegistry
from orion.core.agents.workforce.models import WorkforceAgentContract, WorkforceRole


@dataclass
class AgentTaskResult:
    """Outcome of an individual agent's execution."""

    agent_id: UUID
    role: WorkforceRole
    success: bool
    result: Any
    duration_seconds: float
    error: str | None = None


class WorkforceOrchestrator:
    """Orchestrates sequential and parallel execution across specialized workforce agents."""

    def __init__(
        self,
        registry: WorkforceContractRegistry | None = None,
        max_workers: int = 4,
    ) -> None:
        self.registry = registry or WorkforceContractRegistry.create_default_roster()
        self.max_workers = max_workers
        self._is_cancelled = False

    def cancel_all(self) -> None:
        """Signal cancellation to all in-flight work."""
        self._is_cancelled = True

    def execute_parallel(
        self,
        tasks: list[tuple[WorkforceRole, Callable[[WorkforceAgentContract], Any]]],
        timeout_seconds: float = 30.0,
        reset_cancellation: bool = False,
    ) -> list[AgentTaskResult]:
        """Execute independent tasks concurrently across assigned role contracts."""
        if reset_cancellation:
            self._is_cancelled = False
        results: list[AgentTaskResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_info = {}

            for role, func in tasks:
                agents = self.registry.get_agents_by_role(role)
                contract = agents[0] if agents else self.registry.register_role_contract(role)

                def runner(
                    c: WorkforceAgentContract,
                    fn: Callable[[WorkforceAgentContract], Any],
                ) -> AgentTaskResult:
                    start = datetime.now(UTC)
                    try:
                        if self._is_cancelled:
                            return AgentTaskResult(
                                agent_id=c.agent_id,
                                role=c.role,
                                success=False,
                                result=None,
                                duration_seconds=0.0,
                                error="Cancelled",
                            )
                        out = fn(c)
                        elapsed = (datetime.now(UTC) - start).total_seconds()
                        return AgentTaskResult(
                            agent_id=c.agent_id,
                            role=c.role,
                            success=True,
                            result=out,
                            duration_seconds=elapsed,
                        )
                    except Exception as exc:
                        elapsed = (datetime.now(UTC) - start).total_seconds()
                        return AgentTaskResult(
                            agent_id=c.agent_id,
                            role=c.role,
                            success=False,
                            result=None,
                            duration_seconds=elapsed,
                            error=str(exc),
                        )

                future = executor.submit(runner, contract, func)
                future_to_info[future] = (contract.agent_id, role)

            for future in as_completed(future_to_info, timeout=timeout_seconds):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    aid, r = future_to_info[future]
                    results.append(
                        AgentTaskResult(
                            agent_id=aid,
                            role=r,
                            success=False,
                            result=None,
                            duration_seconds=0.0,
                            error=f"Execution error: {exc}",
                        )
                    )

        return results
