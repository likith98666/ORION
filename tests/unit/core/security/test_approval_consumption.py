from uuid import uuid4

import pytest

from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_repository_memory import (
    InMemoryApprovalRepository,
)
from orion.core.security.approval_service import ApprovalService
from orion.core.security.risk import ToolRiskLevel


def _approved():
    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    agent_id = uuid4()
    execution_id = uuid4()

    request = service.create_request(
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name="send_message",
        action="execute",
        risk_level=ToolRiskLevel.HIGH,
    )

    service.approve(
        request_id=request.id,
        approver="operator",
    )

    return service, repository, request


def test_consume_approval_marks_request_consumed() -> None:
    service, repository, request = _approved()

    consumed = service.consume_approval(
        request_id=request.id,
    )

    assert consumed.status is ApprovalStatus.CONSUMED
    stored = repository.get(request.id)
    assert stored is not None
    assert stored.status is ApprovalStatus.CONSUMED


def test_consumed_approval_cannot_be_consumed_again() -> None:
    service, _, request = _approved()

    service.consume_approval(request_id=request.id)

    with pytest.raises(
        PermissionError,
        match="not available for consumption",
    ):
        service.consume_approval(request_id=request.id)
