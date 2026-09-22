from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.permissions import AgentPermission


class AgentTaskStatus(str, Enum):
    """Lifecycle status of an agent task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """Represents a subtask assigned to an ORION agent."""

    id: UUID
    task_id: UUID
    plan_step_id: UUID | None
    description: str
    required_capability: AgentCapability
    required_permissions: frozenset[AgentPermission] = frozenset()
    expected_requirements: tuple[str, ...] = ()
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    assigned_agent_id: UUID | None = None

    @classmethod
    def create(
        cls,
        task_id: UUID,
        description: str,
        required_capability: AgentCapability,
        plan_step_id: UUID | None = None,
        required_permissions: frozenset[AgentPermission] | None = None,
        expected_requirements: tuple[str, ...] | None = None,
    ) -> "AgentTask":
        """Create a validated ORION agent task."""

        cleaned_description = description.strip()

        if not cleaned_description:
            raise ValueError("Agent task description cannot be empty.")

        if len(cleaned_description) > 5_000:
            raise ValueError(
                "Agent task description cannot exceed 5,000 characters."
            )

        if required_permissions is None:
            required_permissions = frozenset()

        if expected_requirements is None:
            expected_requirements = ()

        cleaned_requirements = tuple(
            requirement.strip()
            for requirement in expected_requirements
        )

        if any(not requirement for requirement in cleaned_requirements):
            raise ValueError(
                "Expected verification requirements cannot be empty."
            )

        if any(len(requirement) > 1_000 for requirement in cleaned_requirements):
            raise ValueError(
                "Expected verification requirements cannot exceed 1,000 characters."
            )

        return cls(
            id=uuid4(),
            task_id=task_id,
            plan_step_id=plan_step_id,
            description=cleaned_description,
            required_capability=required_capability,
            required_permissions=frozenset(required_permissions),
            expected_requirements=cleaned_requirements,
        )
