"""Mission planning, objective decomposition, and deterministic plan validation for V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from orion.core.missions.graph import MissionGraphCycleError, MissionTaskGraph
from orion.core.missions.models import (
    MissionPlan,
    ResourceBudget,
    TaskNode,
    TaskPriority,
    TaskRisk,
)


class PlanValidationError(ValueError):
    """Raised when a candidate plan proposal fails structural or semantic validation."""


@dataclass
class PlanProposal:
    """A proposed mission plan candidate before validation and activation."""

    objective: str
    proposed_tasks: list[dict[str, Any]]
    mission_id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)


class PlanValidator:
    """Deterministic validator verifying that proposed plans satisfy safety and DAG contracts."""

    @staticmethod
    def validate(proposal: PlanProposal) -> tuple[bool, list[str]]:
        """Validate a plan proposal against structural, dependency, and resource rules."""
        errors: list[str] = []

        if not proposal.objective.strip():
            errors.append("Plan proposal must have a non-empty objective.")

        if not proposal.proposed_tasks:
            errors.append("Plan proposal must define at least one task.")
            return False, errors

        task_id_set: set[str] = set()

        for idx, task_data in enumerate(proposal.proposed_tasks):
            t_id = str(task_data.get("task_id", f"task_{idx}"))
            if t_id in task_id_set:
                errors.append(f"Duplicate task ID '{t_id}' detected at index {idx}.")
            task_id_set.add(t_id)

            title = str(task_data.get("title", "")).strip()
            if not title:
                errors.append(f"Task at index {idx} has an empty title.")

            budget = task_data.get("budget", {})
            if isinstance(budget, dict):
                max_dur = budget.get("max_duration_seconds", 300.0)
                if max_dur <= 0:
                    errors.append(f"Task '{title}' has non-positive duration budget: {max_dur}.")
                max_att = budget.get("max_attempts", 3)
                if max_att <= 0:
                    errors.append(f"Task '{title}' has non-positive max_attempts: {max_att}.")

        # Check that all referenced dependencies exist
        for task_data in proposal.proposed_tasks:
            title = str(task_data.get("title", "unnamed"))
            deps = task_data.get("dependencies", [])
            for dep in deps:
                if str(dep) not in task_id_set:
                    errors.append(f"Task '{title}' references nonexistent dependency '{dep}'.")
                if str(dep) == str(task_data.get("task_id", "")):
                    errors.append(f"Task '{title}' cannot depend on itself.")

        # Cycle check using temporary DAG
        if not errors:
            temp_graph = MissionTaskGraph(mission_id=proposal.mission_id)
            node_map: dict[str, TaskNode] = {}
            for t_data in proposal.proposed_tasks:
                node_id = UUID(str(t_data["task_id"])) if "task_id" in t_data else uuid4()
                node = TaskNode(
                    task_id=node_id,
                    title=str(t_data.get("title", "")),
                    description=str(t_data.get("description", "")),
                    priority=TaskPriority(t_data.get("priority", "medium")),
                    risk=TaskRisk(t_data.get("risk", "low")),
                )
                node_map[str(t_data.get("task_id", node_id))] = node

            try:
                for t_data in proposal.proposed_tasks:
                    node = node_map[str(t_data.get("task_id", node.task_id))]
                    temp_graph.add_task(node)

                for t_data in proposal.proposed_tasks:
                    node = node_map[str(t_data.get("task_id", node.task_id))]
                    for dep_str in t_data.get("dependencies", []):
                        dep_node = node_map[str(dep_str)]
                        temp_graph.add_dependency(node.task_id, dep_node.task_id)

                if temp_graph.has_cycles():
                    errors.append("Plan contains circular task dependencies.")
            except (MissionGraphCycleError, ValueError) as exc:
                errors.append(f"Dependency validation failed: {exc}")

        return len(errors) == 0, errors


class MissionPlanner:
    """Decomposes compound high-level user objectives into validated DAG mission plans."""

    def __init__(self, validator: PlanValidator | None = None) -> None:
        self.validator = validator or PlanValidator()

    def decompose_objective(
        self,
        objective: str,
        mission_id: UUID | None = None,
        default_budget: ResourceBudget | None = None,
    ) -> tuple[MissionPlan, MissionTaskGraph]:
        """Decompose a high-level natural language objective into a validated mission plan."""
        mid = mission_id or uuid4()
        budget = default_budget or ResourceBudget()

        # Heuristic / deterministic decomposition into software engineering sub-objectives
        obj_lower = objective.lower()
        sub_tasks: list[dict[str, Any]] = []

        # 1. Repository & failure investigation
        task_1_id = uuid4()
        sub_tasks.append(
            {
                "task_id": str(task_1_id),
                "title": "Diagnose & Inspect Failure Root Cause",
                "description": f"Examine workspace files and isolate fault: {objective}",
                "dependencies": [],
                "priority": "high",
                "risk": "low",
                "budget": budget.to_dict(),
            }
        )

        # 2. Formulate implementation proposal
        task_2_id = uuid4()
        sub_tasks.append(
            {
                "task_id": str(task_2_id),
                "title": "Formulate Solution Architecture & Patch",
                "description": "Design concrete fix without introducing regressions.",
                "dependencies": [str(task_1_id)],
                "priority": "high",
                "risk": "medium",
                "budget": budget.to_dict(),
            }
        )

        # 3. Add regression tests if requested or relevant
        task_3_id: UUID | None = None
        if "test" in obj_lower or "regression" in obj_lower or "bug" in obj_lower:
            task_3_id = uuid4()
            sub_tasks.append(
                {
                    "task_id": str(task_3_id),
                    "title": "Author Targeted Regression Tests",
                    "description": (
                        "Create automated tests reproducing and guarding against recurrence."
                    ),
                    "dependencies": [str(task_2_id)],
                    "priority": "high",
                    "risk": "low",
                    "budget": budget.to_dict(),
                }
            )

        # 4. Apply implementation changes
        task_4_id = uuid4()
        patch_deps = [str(task_3_id)] if task_3_id else [str(task_2_id)]
        sub_tasks.append(
            {
                "task_id": str(task_4_id),
                "title": "Apply Implementation Changes",
                "description": "Apply targeted source edits subject to capability approval.",
                "dependencies": patch_deps,
                "priority": "critical",
                "risk": "high",
                "budget": budget.to_dict(),
            }
        )

        # 5. Run test suite & verify
        task_5_id = uuid4()
        sub_tasks.append(
            {
                "task_id": str(task_5_id),
                "title": "Execute Verification & Integration Suite",
                "description": "Verify 0 regressions and full test pass.",
                "dependencies": [str(task_4_id)],
                "priority": "critical",
                "risk": "medium",
                "budget": budget.to_dict(),
            }
        )

        # 6. Update documentation if requested
        task_6_id: UUID | None = None
        if "doc" in obj_lower or "api" in obj_lower or "readme" in obj_lower:
            task_6_id = uuid4()
            sub_tasks.append(
                {
                    "task_id": str(task_6_id),
                    "title": "Update Documentation & API Contracts",
                    "description": "Align documentation and API references with changes.",
                    "dependencies": [str(task_5_id)],
                    "priority": "medium",
                    "risk": "low",
                    "budget": budget.to_dict(),
                }
            )

        # 7. Final Verification & Certified Report
        task_final_id = uuid4()
        final_deps = [str(task_6_id)] if task_6_id else [str(task_5_id)]
        sub_tasks.append(
            {
                "task_id": str(task_final_id),
                "title": "Final Mission Verification & Certification",
                "description": "Issue authoritative verification certificate and audit report.",
                "dependencies": final_deps,
                "priority": "high",
                "risk": "low",
                "budget": budget.to_dict(),
            }
        )

        proposal = PlanProposal(
            mission_id=mid,
            objective=objective,
            proposed_tasks=sub_tasks,
        )

        is_valid, validation_errors = self.validator.validate(proposal)
        if not is_valid:
            raise PlanValidationError(
                f"Generated plan for objective is invalid: {'; '.join(validation_errors)}"
            )

        # Construct MissionPlan and MissionTaskGraph
        plan = MissionPlan(mission_id=mid, objective=objective)
        graph = MissionTaskGraph(mission_id=mid)

        for task_dict in sub_tasks:
            t_id = UUID(task_dict["task_id"])
            node = TaskNode(
                task_id=t_id,
                title=task_dict["title"],
                description=task_dict["description"],
                dependencies={UUID(d) for d in task_dict.get("dependencies", [])},
                priority=TaskPriority(task_dict.get("priority", "medium")),
                risk=TaskRisk(task_dict.get("risk", "low")),
                budget=budget,
            )
            plan.tasks[t_id] = node
            graph.add_task(node)

        plan.root_task_ids = [t.task_id for t in graph.get_ready_tasks()]
        return plan, graph
