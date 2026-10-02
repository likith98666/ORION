from dataclasses import dataclass

from orion.core.agents.permissions import AgentPermission


@dataclass(frozen=True)
class AgentPermissionPolicy:
    """Defines the permissions granted to an ORION agent."""

    permissions: frozenset[AgentPermission]

    def allows(self, permission: AgentPermission) -> bool:
        """Return whether the requested permission is allowed."""
        return permission in self.permissions

    @classmethod
    def create(
        cls,
        permissions: frozenset[AgentPermission],
    ) -> "AgentPermissionPolicy":
        """Create a permission policy."""
        return cls(
            permissions=frozenset(permissions),
        )
