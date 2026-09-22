from uuid import uuid4

import pytest

from orion.core.security.audit import AuditEvent, AuditEventType
from orion.core.security.audit_repository_memory import InMemoryAuditRepository


def test_save_and_get_audit_event() -> None:
    repository = InMemoryAuditRepository()
    event = AuditEvent.create(AuditEventType.AUTHORIZATION_ALLOWED)

    repository.save(event)

    assert repository.get(event.id) == event


def test_get_unknown_event_returns_none() -> None:
    repository = InMemoryAuditRepository()

    assert repository.get(uuid4()) is None


def test_repository_rejects_invalid_event() -> None:
    repository = InMemoryAuditRepository()

    with pytest.raises(TypeError, match="AuditEvent"):
        repository.save("invalid")


def test_repository_rejects_invalid_event_id() -> None:
    repository = InMemoryAuditRepository()

    with pytest.raises(TypeError, match="UUID"):
        repository.get("invalid")


def test_list_for_agent() -> None:
    repository = InMemoryAuditRepository()
    agent_id = uuid4()

    matching = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_STARTED,
        agent_id=agent_id,
    )
    other = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_STARTED,
        agent_id=uuid4(),
    )

    repository.save(matching)
    repository.save(other)

    assert repository.list_for_agent(agent_id) == [matching]


def test_list_for_execution() -> None:
    repository = InMemoryAuditRepository()
    execution_id = uuid4()

    matching = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_COMPLETED,
        execution_id=execution_id,
    )
    other = AuditEvent.create(
        AuditEventType.TOOL_EXECUTION_COMPLETED,
        execution_id=uuid4(),
    )

    repository.save(matching)
    repository.save(other)

    assert repository.list_for_execution(execution_id) == [matching]


def test_list_for_agent_rejects_invalid_id() -> None:
    repository = InMemoryAuditRepository()

    with pytest.raises(TypeError, match="UUID"):
        repository.list_for_agent("invalid")


def test_list_for_execution_rejects_invalid_id() -> None:
    repository = InMemoryAuditRepository()

    with pytest.raises(TypeError, match="UUID"):
        repository.list_for_execution("invalid")
