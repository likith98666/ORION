"""Contract registry and permission enforcement for workforce agents in V4."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from orion.core.agents.workforce.models import (
    AgentPermissionLevel,
    WorkforceAgentContract,
    WorkforcePermissionError,
    WorkforceRole,
)

DEFAULT_ROLE_TOOLS: dict[WorkforceRole, frozenset[str]] = {
    WorkforceRole.ARCHITECT: frozenset({"list_files", "read_file", "search_files"}),
    WorkforceRole.INVESTIGATOR: frozenset({"list_files", "read_file", "search_files", "diff"}),
    WorkforceRole.IMPLEMENTER: frozenset({"read_file", "diff"}),  # Cannot write directly
    WorkforceRole.TESTER: frozenset({"read_file", "run_tests"}),
    WorkforceRole.REVIEWER: frozenset({"read_file", "diff"}),
    WorkforceRole.SECURITY_ANALYST: frozenset({"read_file", "search_files", "diff"}),
    WorkforceRole.VERIFICATION_AUTHORITY: frozenset({"read_file", "run_tests"}),
}

DEFAULT_ROLE_PERMISSIONS: dict[WorkforceRole, AgentPermissionLevel] = {
    WorkforceRole.ARCHITECT: AgentPermissionLevel.READ_ONLY,
    WorkforceRole.INVESTIGATOR: AgentPermissionLevel.READ_ONLY,
    WorkforceRole.IMPLEMENTER: AgentPermissionLevel.PROPOSE_PATCH,
    WorkforceRole.TESTER: AgentPermissionLevel.EXECUTE_TESTS,
    WorkforceRole.REVIEWER: AgentPermissionLevel.READ_ONLY,
    WorkforceRole.SECURITY_ANALYST: AgentPermissionLevel.READ_ONLY,
    WorkforceRole.VERIFICATION_AUTHORITY: AgentPermissionLevel.VERIFY,
}


class WorkforceContractRegistry:
    """Manages active agent contracts and enforces role-based capability boundaries."""

    def __init__(self) -> None:
        self._contracts: dict[UUID, WorkforceAgentContract] = {}
        self._role_index: dict[WorkforceRole, list[UUID]] = {role: [] for role in WorkforceRole}

    @classmethod
    def create_default_roster(cls) -> WorkforceContractRegistry:
        """Instantiate a registry populated with the canonical workforce roster."""
        registry = cls()
        for role in WorkforceRole:
            registry.register_role_contract(role)
        return registry

    def register_contract(self, contract: WorkforceAgentContract) -> None:
        """Register a specific contract."""
        self._contracts[contract.agent_id] = contract
        self._role_index.setdefault(contract.role, []).append(contract.agent_id)

    def register_role_contract(
        self,
        role: WorkforceRole,
        agent_id: UUID | None = None,
        custom_tools: frozenset[str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> WorkforceAgentContract:
        """Convenience method to register an agent using standard role defaults."""
        aid = agent_id or uuid4()
        perm = DEFAULT_ROLE_PERMISSIONS.get(role, AgentPermissionLevel.READ_ONLY)
        tools = custom_tools or DEFAULT_ROLE_TOOLS.get(role, frozenset())

        contract = WorkforceAgentContract(
            agent_id=aid,
            role=role,
            permission_level=perm,
            allowed_tools=tools,
            budget_timeout_seconds=timeout_seconds,
            evidence_prefix=f"wf:{role.value}",
        )
        self.register_contract(contract)
        return contract

    def get_contract(self, agent_id: UUID) -> WorkforceAgentContract | None:
        """Retrieve contract by agent_id."""
        return self._contracts.get(agent_id)

    def get_agents_by_role(self, role: WorkforceRole) -> list[WorkforceAgentContract]:
        """Retrieve all active agent contracts for a role."""
        ids = self._role_index.get(role, [])
        return [self._contracts[i] for i in ids if i in self._contracts]

    def enforce_tool_call(self, agent_id: UUID, tool_name: str) -> None:
        """Validate that the agent exists and has tool execution permissions."""
        contract = self.get_contract(agent_id)
        if not contract:
            raise WorkforcePermissionError(f"Agent {agent_id} is not registered in the workforce.")
        contract.validate_tool(tool_name)

    def get_roster_summary(self) -> list[dict[str, Any]]:
        """Return serialized roster list for API inspection."""
        return [c.to_dict() for c in self._contracts.values()]
