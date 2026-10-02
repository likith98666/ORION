"""ORION V4 — Advanced Multi-Agent Engineering Package."""

from orion.core.agents.workforce.conflict import AgentConflictResolver
from orion.core.agents.workforce.contracts import (
    DEFAULT_ROLE_PERMISSIONS,
    DEFAULT_ROLE_TOOLS,
    WorkforceContractRegistry,
)
from orion.core.agents.workforce.models import (
    AgentPermissionLevel,
    AgentProposal,
    ConflictResolution,
    ReviewVerdict,
    WorkforceAgentContract,
    WorkforcePermissionError,
    WorkforceRole,
)
from orion.core.agents.workforce.orchestrator import (
    AgentTaskResult,
    WorkforceOrchestrator,
)
from orion.core.agents.workforce.reviewer import IndependentReviewer

__all__ = [
    "AgentConflictResolver",
    "AgentPermissionLevel",
    "AgentProposal",
    "AgentTaskResult",
    "ConflictResolution",
    "DEFAULT_ROLE_PERMISSIONS",
    "DEFAULT_ROLE_TOOLS",
    "IndependentReviewer",
    "ReviewVerdict",
    "WorkforceAgentContract",
    "WorkforceContractRegistry",
    "WorkforceOrchestrator",
    "WorkforcePermissionError",
    "WorkforceRole",
]
