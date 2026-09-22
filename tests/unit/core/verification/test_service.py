from uuid import uuid4

from orion.core.verification.models import (
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository_memory import (
    InMemoryVerificationRepository,
)
from orion.core.verification.service import VerificationService


def test_record_persists_result() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    execution_id = uuid4()

    result = service.record(
        execution_id=execution_id,
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="Output satisfies the expected requirements.",
        metadata={"score": 1.0},
    )

    assert result.execution_id == execution_id
    assert result.status == VerificationStatus.PASSED
    assert repository.get(result.id) == result


def test_get_result() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    result = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.SCHEMA,
        status=VerificationStatus.PASSED,
        reason="Schema is valid.",
    )

    assert service.get(result.id) == result


def test_list_for_execution() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    execution_id = uuid4()

    first = service.record(
        execution_id=execution_id,
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="Output passed.",
    )
    second = service.record(
        execution_id=execution_id,
        verification_type=VerificationType.SCHEMA,
        status=VerificationStatus.PASSED,
        reason="Schema passed.",
    )

    assert service.list_for_execution(execution_id) == [first, second]


def test_list_by_status() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    passed = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="Passed.",
    )
    failed = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.FAILED,
        reason="Failed.",
    )

    assert service.list_by_status(VerificationStatus.PASSED) == [passed]
    assert service.list_by_status(VerificationStatus.FAILED) == [failed]


def test_list_by_type() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    output = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="Output passed.",
    )
    policy = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.POLICY,
        status=VerificationStatus.FAILED,
        reason="Policy failed.",
    )

    assert service.list_by_type(VerificationType.OUTPUT) == [output]
    assert service.list_by_type(VerificationType.POLICY) == [policy]


def test_list_all() -> None:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)

    first = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="First.",
    )
    second = service.record(
        execution_id=uuid4(),
        verification_type=VerificationType.FACTUAL,
        status=VerificationStatus.PENDING,
        reason="Second.",
    )

    assert service.list_all() == [first, second]
