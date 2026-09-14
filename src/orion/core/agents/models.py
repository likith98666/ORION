from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.permission_policy import AgentPermissionPolicy


class AgentStatus(str, Enum):
    """Lifecycle status of an ORION agent."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"


@dataclass
class Agent:
    """Represents a specialized AI agent in ORION."""

    id: UUID
    name: str
    description: str
    capabilities: frozenset[AgentCapability]
    permission_policy: AgentPermissionPolicy
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        capabilities: frozenset[AgentCapability],
        permission_policy: AgentPermissionPolicy | None = None,
    ) -> "Agent":
        """Create a validated ORION agent."""

        cleaned_name = name.strip()
        cleaned_description = description.strip()

        if not cleaned_name:
            raise ValueError("Agent name cannot be empty.")

        if len(cleaned_name) > 200:
            raise ValueError("Agent name cannot exceed 200 characters.")

        if not cleaned_description:
            raise ValueError("Agent description cannot be empty.")

        if len(cleaned_description) > 2_000:
            raise ValueError(
                "Agent description cannot exceed 2,000 characters."
            )

        if not capabilities:
            raise ValueError("Agent must have at least one capability.")

        cleaned_capabilities = frozenset(capabilities)

        if not cleaned_capabilities:
            raise ValueError("Agent must have at least one capability.")

        if permission_policy is None:
            permission_policy = AgentPermissionPolicy.create(
                frozenset()
            )

        return cls(
            id=uuid4(),
            name=cleaned_name,
            description=cleaned_description,
            capabilities=cleaned_capabilities,
            permission_policy=permission_policy,
        )