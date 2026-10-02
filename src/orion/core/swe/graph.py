from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from orion.core.agents.tasks import AgentTask
from orion.core.planning.models import Plan
from orion.core.planning.steps import PlanStep
from orion.core.planning.validator import PlanValidator
from orion.core.swe.stages import (
    DEFAULT_SWE_STAGE_SPECS,
    SWEStepSpec,
    SWETaskStage,
)


@dataclass(frozen=True)
class SWETaskGraph:
    """Deterministic, DAG-validated task graph representing the 7-stage SWE workflow."""

    plan: Plan
    steps: tuple[PlanStep, ...]
    stage_to_step_id: dict[SWETaskStage, UUID]
    step_id_to_stage: dict[UUID, SWETaskStage]
    stage_specs: dict[SWETaskStage, SWEStepSpec]

    @classmethod
    def create(
        cls,
        task_id: UUID,
        objective: str = "Autonomous software engineering mission",
        custom_specs: Mapping[SWETaskStage, SWEStepSpec] | None = None,
    ) -> "SWETaskGraph":
        """Create a deterministically ordered, DAG-validated 7-stage plan and task graph."""
        specs = dict(custom_specs or DEFAULT_SWE_STAGE_SPECS)

        plan = Plan.create(
            task_id=task_id,
            objective=objective,
        )

        canonical_stages = (
            SWETaskStage.INSPECT_REPOSITORY,
            SWETaskStage.ANALYZE_FAILURE,
            SWETaskStage.FORMULATE_FIX,
            SWETaskStage.IMPLEMENT_CHANGE,
            SWETaskStage.RUN_TESTS,
            SWETaskStage.VERIFY,
            SWETaskStage.GENERATE_REPORT,
        )

        steps: list[PlanStep] = []
        stage_to_step_id: dict[SWETaskStage, UUID] = {}
        step_id_to_stage: dict[UUID, SWETaskStage] = {}
        previous_step_id: UUID | None = None

        for idx, stage in enumerate(canonical_stages, start=1):
            spec = specs[stage]
            dependencies = frozenset({previous_step_id}) if previous_step_id else frozenset()

            step = PlanStep.create(
                plan_id=plan.id,
                order=idx,
                description=f"[{spec.name}] {spec.description}",
                required_capability=spec.required_capability,
                dependencies=dependencies,
                priority=3,
            )

            steps.append(step)
            stage_to_step_id[stage] = step.id
            step_id_to_stage[step.id] = stage
            previous_step_id = step.id

        # Validate DAG structure using existing ORION PlanValidator
        validator = PlanValidator()
        validation_result = validator.validate(steps)
        if not validation_result.valid:
            error_details = "; ".join(validation_result.errors)
            raise ValueError(f"SWE task graph failed DAG validation: {error_details}")

        return cls(
            plan=plan,
            steps=tuple(steps),
            stage_to_step_id=stage_to_step_id,
            step_id_to_stage=step_id_to_stage,
            stage_specs=specs,
        )

    def create_agent_tasks(self, task_id: UUID | None = None) -> tuple[AgentTask, ...]:
        """Instantiate ORION AgentTasks mapped to each validated plan step in the graph."""
        effective_task_id = task_id or self.plan.task_id
        tasks: list[AgentTask] = []

        for step in self.steps:
            stage = self.step_id_to_stage[step.id]
            spec = self.stage_specs[stage]

            agent_task = AgentTask.create(
                task_id=effective_task_id,
                plan_step_id=step.id,
                description=step.description,
                required_capability=spec.required_capability,
                required_permissions=spec.required_permissions,
                expected_requirements=spec.expected_requirements,
            )
            tasks.append(agent_task)

        return tuple(tasks)

    def get_step(self, stage: SWETaskStage) -> PlanStep:
        """Retrieve the plan step for a specific stage."""
        step_id = self.stage_to_step_id[stage]
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"Step for stage {stage.value} not found.")

    def get_stage(self, step_id: UUID) -> SWETaskStage:
        """Retrieve the stage for a specific plan step ID."""
        if step_id not in self.step_id_to_stage:
            raise KeyError(f"Plan step ID {step_id} does not map to any SWE stage.")
        return self.step_id_to_stage[step_id]

    def get_spec(self, stage: SWETaskStage) -> SWEStepSpec:
        """Retrieve the specification for a stage."""
        return self.stage_specs[stage]
