from uuid import uuid4

from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import (
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository_memory import (
    InMemoryVerificationRepository,
)
from orion.core.verification.service import VerificationService


def create_engine() -> VerificationEngine:
    repository = InMemoryVerificationRepository()
    service = VerificationService(repository)
    return VerificationEngine(service)


def test_verify_output_passes_when_all_requirements_are_present() -> None:
    engine = create_engine()
    execution_id = uuid4()

    result = engine.verify_output(
        execution_id=execution_id,
        output="The system uses PostgreSQL and Redis.",
        expected_requirements=["PostgreSQL", "Redis"],
    )

    assert result.status == VerificationStatus.PASSED
    assert result.verification_type == VerificationType.OUTPUT
    assert result.metadata["requirements_checked"] == 2


def test_verify_output_fails_when_requirement_is_missing() -> None:
    engine = create_engine()

    result = engine.verify_output(
        execution_id=uuid4(),
        output="The system uses PostgreSQL.",
        expected_requirements=["PostgreSQL", "Redis"],
    )

    assert result.status == VerificationStatus.FAILED
    assert result.metadata["missing_requirements"] == ["Redis"]


def test_verify_output_fails_for_empty_output() -> None:
    engine = create_engine()

    result = engine.verify_output(
        execution_id=uuid4(),
        output="   ",
        expected_requirements=["PostgreSQL"],
    )

    assert result.status == VerificationStatus.FAILED
    assert result.reason == "Execution produced no output."


def test_verify_output_fails_for_none_output() -> None:
    engine = create_engine()

    result = engine.verify_output(
        execution_id=uuid4(),
        output=None,
        expected_requirements=[],
    )

    assert result.status == VerificationStatus.FAILED


def test_verify_output_matching_is_case_insensitive() -> None:
    engine = create_engine()

    result = engine.verify_output(
        execution_id=uuid4(),
        output="The system uses POSTGRESQL.",
        expected_requirements=["postgresql"],
    )

    assert result.status == VerificationStatus.PASSED


def test_verify_output_records_execution_id() -> None:
    engine = create_engine()
    execution_id = uuid4()

    result = engine.verify_output(
        execution_id=execution_id,
        output="Everything passed.",
        expected_requirements=[],
    )

    assert result.execution_id == execution_id


def test_verify_output_allows_no_requirements() -> None:
    engine = create_engine()

    result = engine.verify_output(
        execution_id=uuid4(),
        output="Valid output.",
        expected_requirements=[],
    )

    assert result.status == VerificationStatus.PASSED
    assert result.metadata["requirements_checked"] == 0
