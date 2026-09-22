from uuid import uuid4

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository_memory import (
    InMemoryVerificationRepository,
)


def create_result(
    *,
    execution_id=None,
    verification_type=VerificationType.OUTPUT,
    status=VerificationStatus.PASSED,
    reason="Verification passed.",
):
    return VerificationResult.create(
        execution_id=execution_id or uuid4(),
        verification_type=verification_type,
        status=status,
        reason=reason,
    )


def test_save_and_get() -> None:
    repository = InMemoryVerificationRepository()
    result = create_result()

    repository.save(result)

    assert repository.get(result.id) == result


def test_get_missing_returns_none() -> None:
    repository = InMemoryVerificationRepository()

    assert repository.get(uuid4()) is None


def test_list_for_execution() -> None:
    repository = InMemoryVerificationRepository()
    execution_id = uuid4()

    first = create_result(execution_id=execution_id)
    second = create_result(execution_id=execution_id)
    other = create_result()

    repository.save(first)
    repository.save(second)
    repository.save(other)

    assert repository.list_for_execution(execution_id) == [
        first,
        second,
    ]


def test_list_by_status() -> None:
    repository = InMemoryVerificationRepository()

    passed = create_result(status=VerificationStatus.PASSED)
    failed = create_result(status=VerificationStatus.FAILED)

    repository.save(passed)
    repository.save(failed)

    assert repository.list_by_status(VerificationStatus.PASSED) == [passed]
    assert repository.list_by_status(VerificationStatus.FAILED) == [failed]


def test_list_by_type() -> None:
    repository = InMemoryVerificationRepository()

    output = create_result(
        verification_type=VerificationType.OUTPUT,
    )
    schema = create_result(
        verification_type=VerificationType.SCHEMA,
    )

    repository.save(output)
    repository.save(schema)

    assert repository.list_by_type(VerificationType.OUTPUT) == [output]
    assert repository.list_by_type(VerificationType.SCHEMA) == [schema]


def test_list_all() -> None:
    repository = InMemoryVerificationRepository()

    first = create_result()
    second = create_result()

    repository.save(first)
    repository.save(second)

    assert repository.list_all() == [first, second]


def test_save_replaces_existing_result() -> None:
    repository = InMemoryVerificationRepository()
    result = create_result()

    repository.save(result)

    result.reason = "Updated verification result."
    repository.save(result)

    stored = repository.get(result.id)

    assert stored is result
    assert stored.reason == "Updated verification result."
