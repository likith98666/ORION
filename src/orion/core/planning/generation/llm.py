import json
from uuid import UUID

from orion.config.model_config import ModelConfig
from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.generation.models import (
    GeneratedPlan,
    GeneratedPlanStep,
)
from orion.core.planning.generation.schema import PlanResponseSchema
from orion.models.contracts import ModelRequest
from orion.models.runtime.runtime import ModelRuntime


class LLMPlanGenerator(PlanGenerator):
    """Generate structured plans using an ORION model runtime."""

    def __init__(
        self,
        runtime: ModelRuntime,
        config: ModelConfig,
    ) -> None:
        self._runtime = runtime
        self._config = config

    def generate(
        self,
        task_id: UUID,
        objective: str,
    ) -> GeneratedPlan:
        """Generate a structured plan from a natural-language objective."""

        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Plan generation objective cannot be empty.")

        request = ModelRequest(
            prompt=self._build_prompt(cleaned_objective),
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )

        response = self._runtime.generate(
            config=self._config,
            request=request,
        )

        return self._parse_response(
            task_id=task_id,
            objective=cleaned_objective,
            response_text=response.text,
        )

    @staticmethod
    def _build_prompt(objective: str) -> str:
        """Build the planning prompt supplied to the model."""

        return (
            "Create a structured execution plan for the following objective.\n\n"
            f"Objective: {objective}\n\n"
            "Return ONLY valid JSON using exactly this structure:\n"
            "{\n"
            '  "steps": [\n'
            "    {\n"
            '      "order": 1,\n'
            '      "description": "Actionable step description",\n'
            '      "required_capability": "research",\n'
            '      "dependencies": []\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Each step must have a unique positive integer order.\n"
            "- Each step must contain an actionable description.\n"
            "- Each description must be actionable and non-empty.\n"
            "- required_capability must be a valid ORION agent capability.\n"
            "- dependencies must contain step order numbers.\n"
            "- Dependencies must reference existing steps.\n"
            "- A step cannot depend on itself.\n"
            "- Return JSON only. Do not include markdown or explanations."
        )

    @staticmethod
    def _parse_response(
        task_id: UUID,
        objective: str,
        response_text: str,
    ) -> GeneratedPlan:
        """Parse and validate a JSON model response into a generated plan."""

        cleaned_response = response_text.strip()

        if not cleaned_response:
            raise ValueError("LLM plan response cannot be empty.")

        try:
            decoded_response = json.loads(cleaned_response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM plan response must contain valid JSON."
            ) from exc

        if not isinstance(decoded_response, dict):
            raise ValueError("LLM plan response must be a JSON object.")

        schema = PlanResponseSchema.from_dict(decoded_response)

        steps = tuple(
            GeneratedPlanStep(
                order=step.order,
                description=step.description,
                required_capability=step.required_capability,
                dependencies=step.dependencies,
            )
            for step in schema.steps
        )

        return GeneratedPlan.create(
            task_id=task_id,
            objective=objective,
            steps=steps,
        )