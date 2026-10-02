"""Change impact analysis calculating affected modules, tests, and regression risk in V3."""

from __future__ import annotations

from collections.abc import Sequence

from orion.core.repo_intel.graph import RepoCodeGraph
from orion.core.repo_intel.models import ImpactReport


class ChangeImpactAnalyzer:
    """Evaluates the structural blast radius of proposed file and symbol modifications."""

    def __init__(self, code_graph: RepoCodeGraph) -> None:
        self.code_graph = code_graph

    def analyze_change(
        self,
        target_file: str,
        modified_symbols: Sequence[str] | None = None,
    ) -> ImpactReport:
        """Analyze the direct and transitive impact of modifying target_file."""
        norm_target = target_file.replace("\\", "/")

        direct_dependents = self.code_graph.get_dependents(norm_target, recursive=False)
        transitive_dependents = self.code_graph.get_dependents(norm_target, recursive=True)

        # Collect all affected tests
        impacted_tests: set[str] = set()

        # Direct tests for the target file
        for t in self.code_graph.get_tests_for_file(norm_target):
            impacted_tests.add(t)

        # Tests covering direct and transitive dependents
        for dep in transitive_dependents:
            for t in self.code_graph.get_tests_for_file(dep):
                impacted_tests.add(t)
            # If the dependent itself is a test file
            dep_node = self.code_graph.modules.get(dep)
            if dep_node and dep_node.is_test:
                impacted_tests.add(dep)

        # Calculate regression risk score based on blast radius
        total_affected = len(transitive_dependents)
        if total_affected == 0:
            risk = "low"
        elif total_affected <= 2:
            risk = "medium"
        elif total_affected <= 6:
            risk = "high"
        else:
            risk = "critical"

        # Elevated risk if modified symbols are extensively referenced
        symbols_tuple = tuple(modified_symbols or ())

        return ImpactReport(
            target_file=norm_target,
            modified_symbols=symbols_tuple,
            directly_affected_modules=tuple(sorted(direct_dependents)),
            transitively_affected_modules=tuple(sorted(transitive_dependents)),
            impacted_tests=tuple(sorted(impacted_tests)),
            regression_risk=risk,
        )
