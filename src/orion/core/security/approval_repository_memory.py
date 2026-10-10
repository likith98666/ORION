from uuid import UUID

from orion.core.security.approval import ApprovalRequest
from orion.core.security.approval_repository import ApprovalRepository


class InMemoryApprovalRepository(ApprovalRepository):
    """In-memory approval repository for deterministic execution and tests."""

    def __init__(self) -> None:
        self._requests: dict[UUID, ApprovalRequest] = {}

    def save(self, request: ApprovalRequest) -> None:
        if not isinstance(request, ApprovalRequest):
            raise TypeError("request must be an ApprovalRequest.")

        self._requests[request.id] = request

    def get(self, request_id: UUID) -> ApprovalRequest | None:
        if not isinstance(request_id, UUID):
            raise TypeError("request_id must be a UUID.")

        return self._requests.get(request_id)
