from uuid import UUID, uuid4

import pytest

from orion.config.model_config import ModelConfig
from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.generation.llm import LLMPlanGenerator
from orion.core.planning.generation.models import GeneratedPlan
from orion.models.contracts import ModelRequest, ModelResponse


def valid_plan_response() -> str:
    """Return a valid structured plan response."""

    return """
    {
        "steps": [
            {
                "order": 1,
                "description": "Collect relevant information",
                "required_capability": "research",
                "dependencies": []
            },
            {
                "order": 2,
                "description": "Analyze the information",
                "required_capability": "data_analysis",
                "dependencies": [1]
            }
        ]
    }
    """


class FakeRuntime:
    """Fake model runtime for deterministic unit tests."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.received_config: ModelConfig | None = None
        self.received_request: ModelRequest | None = None

    def generate(
        self,
        config: ModelConfig,
        request: ModelRequest,
    ) -> ModelResponse:
        self.received_config = config
        self.received_request = request

        return ModelResponse(
            text=self.response_text,
            model_name="fake-model",
            provider_name=config.provider_name,
            input_tokens=10,
            output_tokens=20,
            latency_ms=5.0,
        )


def test_generate_builds_model_request() -> None:
    runtime = FakeRuntime(valid_plan_response())

    config = ModelConfig(
        provider_name="mock",
        temperature=0.0,
        max_tokens=500,
    )

    generator = LLMPlanGenerator(
        runtime=runtime,
        config=config,
    )

    task_id = uuid4()

    result = generator.generate(
        task_id=task_id,
        objective="Research AI platforms",
    )

    assert isinstance(result, GeneratedPlan)
    assert result.task_id == task_id
    assert runtime.received_config == config
    assert runtime.received_request is not None
    assert "Research AI platforms" in runtime.received_request.prompt
    assert runtime.received_request.temperature == 0.0
    assert runtime.received_request.max_tokens == 500


def test_generate_strips_objective_before_sending_request() -> None:
    runtime = FakeRuntime(valid_plan_response())

    config = ModelConfig(
        provider_name="mock",
    )

    generator = LLMPlanGenerator(
        runtime=runtime,
        config=config,
    )

    generator.generate(
        task_id=uuid4(),
        objective="  Research AI platforms  ",
    )

    assert runtime.received_request is not None
    assert "Objective: Research AI platforms" in runtime.received_request.prompt
    assert "Objective:   Research AI platforms  " not in (
        runtime.received_request.prompt
    )


def test_generate_rejects_empty_objective() -> None:
    runtime = FakeRuntime(valid_plan_response())

    config = ModelConfig(
        provider_name="mock",
    )

    generator = LLMPlanGenerator(
        runtime=runtime,
        config=config,
    )

    with pytest.raises(
        ValueError,
        match="Plan generation objective cannot be empty.",
    ):
        generator.generate(
            task_id=uuid4(),
            objective="   ",
        )


def test_build_prompt_contains_required_planning_instructions() -> None:
    prompt = LLMPlanGenerator._build_prompt(
        "Analyze customer feedback",
    )

    assert "structured execution plan" in prompt
    assert "Analyze customer feedback" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "actionable description" in prompt
    assert "required_capability" in prompt
    assert "dependencies" in prompt
    assert "Return JSON only" in prompt


def test_parse_response_returns_generated_plan() -> None:
    task_id = uuid4()

    result = LLMPlanGenerator._parse_response(
        task_id=task_id,
        objective="Research AI platforms",
        response_text=valid_plan_response(),
    )

    assert isinstance(result, GeneratedPlan)
    assert result.task_id == task_id
    assert result.objective == "Research AI platforms"
    assert len(result.steps) == 2

    assert result.steps[0].order == 1
    assert result.steps[0].required_capability == AgentCapability.RESEARCH

    assert result.steps[1].order == 2
    assert (
        result.steps[1].required_capability
        == AgentCapability.DATA_ANALYSIS
    )
    assert result.steps[1].dependencies == frozenset({1})


def test_parse_response_rejects_empty_response() -> None:
    with pytest.raises(
        ValueError,
        match="LLM plan response cannot be empty.",
    ):
        LLMPlanGenerator._parse_response(
            task_id=uuid4(),
            objective="Research AI platforms",
            response_text="   ",
        )


def test_parse_response_rejects_invalid_json() -> None:
    with pytest.raises(
        ValueError,
        match="LLM plan response must contain valid JSON.",
    ):
        LLMPlanGenerator._parse_response(
            task_id=uuid4(),
            objective="Research AI platforms",
            response_text="not json",
        )


def test_parse_response_rejects_non_object_json() -> None:
    with pytest.raises(
        ValueError,
        match="LLM plan response must be a JSON object.",
    ):
        LLMPlanGenerator._parse_response(
            task_id=uuid4(),
            objective="Research AI platforms",
            response_text="[]",
        )


def test_parse_response_rejects_invalid_plan_schema() -> None:
    invalid_response = """
    {
        "steps": [
            {
                "order": 1,
                "description": "Research",
                "required_capability": "invalid",
                "dependencies": []
            }
        ]
    }
    """

    with pytest.raises(
        ValueError,
        match="Unknown agent capability: invalid",
    ):
        LLMPlanGenerator._parse_response(
            task_id=uuid4(),
            objective="Research AI platforms",
            response_text=invalid_response,
        )


def test_llm_plan_generator_implements_plan_generator_contract() -> None:
    runtime = FakeRuntime(valid_plan_response())

    config = ModelConfig(
        provider_name="mock",
    )

    generator = LLMPlanGenerator(
        runtime=runtime,
        config=config,
    )

    assert isinstance(generator, PlanGenerator)


def test_generate_uses_configured_model_settings() -> None:
    runtime = FakeRuntime(valid_plan_response())

    config = ModelConfig(
        provider_name="alternate",
        temperature=0.4,
        max_tokens=750,
    )

    generator = LLMPlanGenerator(
        runtime=runtime,
        config=config,
    )

    generator.generate(
        task_id=uuid4(),
        objective="Analyze software repositories",
    )

    assert runtime.received_config == config
    assert runtime.received_request is not None
    assert runtime.received_request.temperature == 0.4
    assert runtime.received_request.max_tokens == 750