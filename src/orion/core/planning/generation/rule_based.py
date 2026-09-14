from uuid import UUID

from orion.core.agents.capabilities import AgentCapability
from orion.core.planning.generation.generator import PlanGenerator
from orion.core.planning.generation.models import (
    GeneratedPlan,
    GeneratedPlanStep,
)


class RuleBasedPlanGenerator(PlanGenerator):
    """Generate deterministic plans using simple objective classification."""

    def generate(
        self,
        task_id: UUID,
        objective: str,
    ) -> GeneratedPlan:
        """Generate a deterministic plan for the supplied objective."""

        cleaned_objective = objective.strip()

        if not cleaned_objective:
            raise ValueError("Plan generation objective cannot be empty.")

        steps = self._generate_steps(cleaned_objective)

        return GeneratedPlan.create(
            task_id=task_id,
            objective=cleaned_objective,
            steps=steps,
        )

    def _generate_steps(
        self,
        objective: str,
    ) -> tuple[GeneratedPlanStep, ...]:
        """Select a deterministic workflow based on objective keywords."""

        normalized_objective = objective.lower()

        if any(
            keyword in normalized_objective
            for keyword in ("research", "investigate", "study")
        ):
            return self._research_plan()

        if any(
            keyword in normalized_objective
            for keyword in ("analyze", "analysis", "dataset", "data")
        ):
            return self._data_analysis_plan()

        if any(
            keyword in normalized_objective
            for keyword in ("code", "software", "repository", "program")
        ):
            return self._software_plan()

        return self._general_plan()

    @staticmethod
    def _research_plan() -> tuple[GeneratedPlanStep, ...]:
        return (
            GeneratedPlanStep(
                order=1,
                description="Collect relevant information",
                required_capability=AgentCapability.RESEARCH,
            ),
            GeneratedPlanStep(
                order=2,
                description="Analyze the collected information",
                required_capability=AgentCapability.REASONING,
                dependencies=frozenset({1}),
            ),
            GeneratedPlanStep(
                order=3,
                description="Write the final findings",
                required_capability=AgentCapability.WRITING,
                dependencies=frozenset({2}),
            ),
        )

    @staticmethod
    def _data_analysis_plan() -> tuple[GeneratedPlanStep, ...]:
        return (
            GeneratedPlanStep(
                order=1,
                description="Inspect and prepare the data",
                required_capability=AgentCapability.DATA_ANALYSIS,
            ),
            GeneratedPlanStep(
                order=2,
                description="Analyze the data",
                required_capability=AgentCapability.DATA_ANALYSIS,
                dependencies=frozenset({1}),
            ),
            GeneratedPlanStep(
                order=3,
                description="Summarize the analysis results",
                required_capability=AgentCapability.WRITING,
                dependencies=frozenset({2}),
            ),
        )

    @staticmethod
    def _software_plan() -> tuple[GeneratedPlanStep, ...]:
        return (
            GeneratedPlanStep(
                order=1,
                description="Inspect the software context",
                required_capability=AgentCapability.REASONING,
            ),
            GeneratedPlanStep(
                order=2,
                description="Implement or modify the required solution",
                required_capability=AgentCapability.CODE_EXECUTION,
                dependencies=frozenset({1}),
            ),
            GeneratedPlanStep(
                order=3,
                description="Verify the implementation",
                required_capability=AgentCapability.VERIFICATION,
                dependencies=frozenset({2}),
            ),
        )

    @staticmethod
    def _general_plan() -> tuple[GeneratedPlanStep, ...]:
        return (
            GeneratedPlanStep(
                order=1,
                description="Understand the objective",
                required_capability=AgentCapability.REASONING,
            ),
            GeneratedPlanStep(
                order=2,
                description="Execute the required work",
                required_capability=AgentCapability.REASONING,
                dependencies=frozenset({1}),
            ),
            GeneratedPlanStep(
                order=3,
                description="Prepare the final result",
                required_capability=AgentCapability.WRITING,
                dependencies=frozenset({2}),
            ),
        )