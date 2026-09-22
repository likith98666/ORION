from uuid import uuid4

import pytest

from orion.core.security.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
    SecurityContext,
)


def test_security_context_requires_agent_id():
    with pytest.raises(TypeError, match="agent_id must be a UUID"):
        SecurityContext(agent_id="not-a-uuid")  # type: ignore[arg-type]


def test_security_context_accepts_execution_scope():
    agent_id = uuid4()
    task_id = uuid4()
    execution_id = uuid4()

    context = SecurityContext(
        agent_id=agent_id,
        task_id=task_id,
        execution_id=execution_id,
    )

    assert context.agent_id == agent_id
    assert context.task_id == task_id
    assert context.execution_id == execution_id


def test_security_context_is_immutable():
    context = SecurityContext(agent_id=uuid4())

    with pytest.raises(AttributeError):
        context.agent_id = uuid4()  # type: ignore[misc]


def test_authorization_request_normalizes_resource_and_action():
    context = SecurityContext(agent_id=uuid4())

    request = AuthorizationRequest(
        context=context,
        resource="  tool:database  ",
        action="  write  ",
    )

    assert request.resource == "tool:database"
    assert request.action == "write"


def test_authorization_request_rejects_empty_resource():
    context = SecurityContext(agent_id=uuid4())

    with pytest.raises(
        ValueError,
        match="Authorization resource cannot be empty",
    ):
        AuthorizationRequest(
            context=context,
            resource="   ",
            action="execute",
        )


def test_authorization_request_rejects_empty_action():
    context = SecurityContext(agent_id=uuid4())

    with pytest.raises(
        ValueError,
        match="Authorization action cannot be empty",
    ):
        AuthorizationRequest(
            context=context,
            resource="tool:database",
            action="   ",
        )


def test_authorization_result_allows_execution():
    result = AuthorizationResult(
        decision=AuthorizationDecision.ALLOW,
        reason="Agent has the required authorization.",
    )

    assert result.allowed is True


def test_authorization_result_denies_execution():
    result = AuthorizationResult(
        decision=AuthorizationDecision.DENY,
        reason="Required permission is missing.",
    )

    assert result.allowed is False


def test_authorization_result_requires_non_empty_reason():
    with pytest.raises(
        ValueError,
        match="Authorization reason cannot be empty",
    ):
        AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason="   ",
        )


def test_authorization_result_is_immutable():
    result = AuthorizationResult(
        decision=AuthorizationDecision.ALLOW,
        reason="Authorized.",
    )

    with pytest.raises(AttributeError):
        result.decision = AuthorizationDecision.DENY  # type: ignore[misc]


def test_authorization_decisions_are_string_compatible():
    assert AuthorizationDecision.ALLOW == "allow"
    assert AuthorizationDecision.DENY == "deny"
    assert AuthorizationDecision.REQUIRE_APPROVAL == "require_approval"
