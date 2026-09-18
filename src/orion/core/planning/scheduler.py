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
            key=lambda step: (-step.priority, step.order),
        )

    def mark_ready_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:
        """Transition all currently executable pending steps to READY."""

        ready_steps = self.get_ready_steps(steps)

        for step in ready_steps:
            step.status = PlanStepStatus.READY

        return ready_steps

    def get_blocked_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:
        """Return pending steps blocked by failed or skipped dependencies."""

        terminal_blocking_ids = {
            step.id
            for step in steps
            if step.status in {
                PlanStepStatus.FAILED,
                PlanStepStatus.SKIPPED,
            }
        }

        blocked_steps: list[PlanStep] = []

        for step in steps:
            if step.status != PlanStepStatus.PENDING:
                continue

            if step.dependencies.intersection(terminal_blocking_ids):
                blocked_steps.append(step)

        return sorted(
            blocked_steps,
            key=lambda step: (-step.priority, step.order),
        )

    def mark_blocked_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:
        """Transition steps with failed or skipped dependencies to SKIPPED."""

        blocked_steps = self.get_blocked_steps(steps)

        for step in blocked_steps:
            step.status = PlanStepStatus.SKIPPED

        return blocked_steps


