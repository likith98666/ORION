from orion.core.planning.steps import PlanStep, PlanStepStatus


class PlanScheduler:
    """Determines which ORION plan steps are ready to execute."""

    def get_ready_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:
        """Return pending steps whose dependencies are completed."""

        completed_ids = {
            step.id
            for step in steps
            if step.status == PlanStepStatus.COMPLETED
        }

        ready_steps: list[PlanStep] = []

        for step in steps:
            if step.status != PlanStepStatus.PENDING:
                continue

            if step.dependencies.issubset(completed_ids):
                ready_steps.append(step)

        return sorted(
            ready_steps,
            key=lambda step: step.order,
        )