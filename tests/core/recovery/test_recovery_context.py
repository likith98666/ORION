import pytest

from orion.core.recovery.recovery_context import RecoveryContext


def test_creates_valid_context() -> None:
    context = RecoveryContext(
        retry_count=1,
        max_retries=3,
        task_criticality=0.8,
        alternative_agents_available=True,
        alternative_tools_available=False,
        alternative_models_available=True,
        remaining_budget=10.0,
        remaining_time_ms=5000.0,
    )

    assert context.retry_count == 1
    assert context.max_retries == 3
    assert context.task_criticality == 0.8
    assert context.alternative_agents_available is True
    assert context.alternative_tools_available is False
    assert context.alternative_models_available is True
    assert context.remaining_budget == 10.0
    assert context.remaining_time_ms == 5000.0


def test_context_is_immutable() -> None:
    context = RecoveryContext()

    with pytest.raises(AttributeError):
        context.retry_count = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retry_count", -1),
        ("max_retries", -1),
        ("task_criticality", -0.1),
        ("task_criticality", 1.1),
        ("remaining_budget", -1.0),
        ("remaining_time_ms", -1.0),
    ],
)
def test_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        RecoveryContext(**{field: value})


def test_rejects_retry_count_greater_than_max_retries() -> None:
    with pytest.raises(ValueError, match="retry_count"):
        RecoveryContext(
            retry_count=4,
            max_retries=3,
        )


def test_allows_zero_remaining_budget() -> None:
    context = RecoveryContext(remaining_budget=0.0)

    assert context.remaining_budget == 0.0


def test_allows_zero_remaining_time() -> None:
    context = RecoveryContext(remaining_time_ms=0.0)

    assert context.remaining_time_ms == 0.0


def test_defaults_are_safe() -> None:
    context = RecoveryContext()

    assert context.retry_count == 0
    assert context.max_retries == 3
    assert context.task_criticality == 0.5
    assert context.alternative_agents_available is False
    assert context.alternative_tools_available is False
    assert context.alternative_models_available is False
    assert context.remaining_budget == 0.0
    assert context.remaining_time_ms == 0.0
