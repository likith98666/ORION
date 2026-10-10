from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.security.approval import ApprovalRequest


class ApprovalRepository(ABC):
    """Persistence contract for high-risk approval requests."""

    @abstractmethod
    def save(self, request: ApprovalRequest) -> None:
        """Persist an approval request."""
        raise NotImplementedError

    @abstractmethod
    def get(self, request_id: UUID) -> ApprovalRequest | None:
        """Retrieve an approval request by identifier."""
        raise NotImplementedError
