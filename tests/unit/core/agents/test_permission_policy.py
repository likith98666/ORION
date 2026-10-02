import pytest

from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission


def test_policy_can_be_created() -> None:
    policy = AgentPermissionPolicy.create(
        frozenset(
            {
                AgentPermission.READ_FILES,
                AgentPermission.WEB_ACCESS,
            }
        )
    )

    assert policy.permissions == frozenset(
        {
            AgentPermission.READ_FILES,
            AgentPermission.WEB_ACCESS,
        }
    )


def test_policy_allows_granted_permission() -> None:
    policy = AgentPermissionPolicy.create(frozenset({AgentPermission.WEB_ACCESS}))

    assert policy.allows(AgentPermission.WEB_ACCESS) is True


def test_policy_denies_ungranted_permission() -> None:
    policy = AgentPermissionPolicy.create(frozenset({AgentPermission.WEB_ACCESS}))

    assert policy.allows(AgentPermission.CODE_EXECUTION) is False


def test_policy_removes_duplicate_permissions() -> None:
    policy = AgentPermissionPolicy.create(
        frozenset(
            {
                AgentPermission.READ_FILES,
                AgentPermission.READ_FILES,
            }
        )
    )

    assert len(policy.permissions) == 1


def test_policy_is_immutable() -> None:
    policy = AgentPermissionPolicy.create(frozenset({AgentPermission.READ_FILES}))

    with pytest.raises(AttributeError):
        policy.permissions = frozenset({AgentPermission.WEB_ACCESS})  # type: ignore[misc]
