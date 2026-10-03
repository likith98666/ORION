"""Deterministic, bounded test-target selection component for SWE missions."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from orion.core.swe.execution.errors import ControlledExecutionError
from orion.core.workspace.errors import PathOutsideWorkspaceError, PathSecurityError
from orion.core.workspace.models import Workspace

MAX_BOUNDED_TESTS: int = 10
MAX_BOUNDED_FALLBACK_COUNT: int = 3

DEFAULT_FALLBACK_CANDIDATES: tuple[str, ...] = (
    "tests/smoke/test_smoke.py",
    "tests/test_smoke.py",
    "tests/unit/test_smoke.py",
    "tests/unit/core/swe/test_task_graph.py",
    "tests/unit/api/test_product_api.py",
)


class TestSelectionStrategy(str, Enum):
    """Categorized strategies for determining test targets."""

    __test__ = False

    EXPLICIT_TEST_TARGET = "EXPLICIT_TEST_TARGET"
    DIRECT_TEST_MAPPING = "DIRECT_TEST_MAPPING"
    PACKAGE_MAPPING = "PACKAGE_MAPPING"
    FAILURE_LOCATION_MAPPING = "FAILURE_LOCATION_MAPPING"
    SAFE_BOUNDED_FALLBACK = "SAFE_BOUNDED_FALLBACK"


@dataclass(frozen=True)
class TestSelectionResult:
    """Authoritative result of deterministic test-target selection."""

    __test__ = False

    selected_tests: tuple[str, ...]
    strategy: TestSelectionStrategy
    reason: str
    is_explicit: bool
    is_fallback: bool
    target_spec: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert test selection result to a dictionary representation."""
        return {
            "selected_tests": list(self.selected_tests),
            "strategy": self.strategy.value,
            "reason": self.reason,
            "is_explicit": self.is_explicit,
            "is_fallback": self.is_fallback,
            "target_spec": self.target_spec,
            "metadata": dict(self.metadata),
        }


class TestTargetSelector:
    """Deterministic, inspectable test-target selector for bounded SWE execution."""

    __test__ = False

    def __init__(
        self,
        workspace: Workspace,
        default_fallback_targets: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be a Workspace instance.")
        self._workspace = workspace
        self._default_fallback_targets = (
            tuple(default_fallback_targets) if default_fallback_targets else ()
        )

    @property
    def workspace(self) -> Workspace:
        """Return the bound workspace."""
        return self._workspace

    def _validate_single_target(self, target_str: str) -> str:
        """Validate an individual test target path against workspace safety boundaries."""
        t = target_str.strip()
        if not t:
            raise ControlledExecutionError("Empty test target path encountered.")

        # Prohibit null bytes and path traversal components
        norm_slashes = t.replace("\\", "/")
        if "\0" in t or ".." in norm_slashes.split("/"):
            raise ControlledExecutionError(
                f"Target path '{t}' contains forbidden sequences or directory traversal."
            )

        # Separate node ID if present (e.g., tests/test_foo.py::test_case)
        base_part = norm_slashes.split("::")[0] if "::" in norm_slashes else norm_slashes
        sub_part = f"::{norm_slashes.split('::', 1)[1]}" if "::" in norm_slashes else ""

        try:
            resolved = self._workspace.validate_path(base_part)
            rel = str(self._workspace.relative_path(resolved)).replace("\\", "/")
            return f"{rel}{sub_part}"
        except (PathOutsideWorkspaceError, PathSecurityError, ValueError) as exc:
            raise ControlledExecutionError(
                f"Target path '{t}' escapes workspace boundary: {exc}"
            ) from exc

    def _find_direct_tests(self, file_path_str: str) -> list[str]:
        """Derive direct test file candidates for a given source or test file."""
        norm = file_path_str.replace("\\", "/").strip().lstrip("./")
        if not norm:
            return []

        # If already a test file, verify containment and existence
        p = Path(norm)
        if norm.startswith("tests/") or p.name.startswith("test_") or p.name.endswith("_test.py"):
            target_path = self._workspace.repository_root / norm
            if target_path.is_file():
                try:
                    return [self._validate_single_target(norm)]
                except ControlledExecutionError:
                    return []

        stem = p.stem
        matches: list[str] = []

        # 1. Direct naming conventions
        candidates = [
            f"tests/test_{stem}.py",
            f"tests/unit/test_{stem}.py",
            f"tests/{stem}_test.py",
            f"tests/unit/{stem}_test.py",
        ]

        # Consider subpackage hierarchy (e.g., src/orion/api/service.py -> api)
        parts = [part for part in p.parts if part not in ("src", "lib", "app", p.name)]
        if parts:
            last_pkg = parts[-1]
            subpath = "/".join(parts)
            candidates.extend([
                f"tests/unit/{subpath}/test_{stem}.py",
                f"tests/{subpath}/test_{stem}.py",
                f"tests/unit/{last_pkg}/test_{stem}.py",
                f"tests/{last_pkg}/test_{stem}.py",
                f"tests/unit/{last_pkg}/test_mission_{stem}.py",
                f"tests/unit/{last_pkg}/test_product_{last_pkg}.py",
            ])

        for cand in candidates:
            cand_path = self._workspace.repository_root / cand
            if cand_path.is_file():
                try:
                    matches.append(self._validate_single_target(cand))
                except ControlledExecutionError:
                    continue

        if matches:
            return matches

        # 2. Search for test files matching test_*{stem}*.py under tests/
        tests_dir = self._workspace.repository_root / "tests"
        if tests_dir.is_dir():
            for test_file in tests_dir.rglob(f"test_*{stem}*.py"):
                if test_file.is_file():
                    try:
                        rel = str(test_file.relative_to(self._workspace.repository_root)).replace(
                            "\\", "/"
                        )
                        matches.append(self._validate_single_target(rel))
                    except (ValueError, ControlledExecutionError):
                        continue

        return matches

    def _find_package_tests(self, file_path_str: str) -> list[str]:
        """Derive package/domain test files for a given source file."""
        norm = file_path_str.replace("\\", "/").strip().lstrip("./")
        p = Path(norm)
        parts = [part for part in p.parts if part not in ("src", "lib", "app", p.name)]
        if not parts:
            return []

        pkg_candidates: list[str] = []
        pkg_candidates.append("/".join(parts))
        if len(parts) > 1:
            pkg_candidates.append("/".join(parts[1:]))
        pkg_candidates.append(parts[-1])

        for pkg in pkg_candidates:
            for prefix in ("tests/unit", "tests", "tests/integration"):
                cand_dir = self._workspace.repository_root / prefix / pkg
                if cand_dir.is_dir():
                    found: list[str] = []
                    for f in sorted(cand_dir.iterdir()):
                        if (
                            f.is_file()
                            and f.suffix == ".py"
                            and (f.name.startswith("test_") or f.name.endswith("_test.py"))
                        ):
                            try:
                                rel = str(
                                    f.relative_to(self._workspace.repository_root)
                                ).replace("\\", "/")
                                found.append(self._validate_single_target(rel))
                                if len(found) >= MAX_BOUNDED_TESTS:
                                    break
                            except (ValueError, ControlledExecutionError):
                                continue
                    if found:
                        return found
        return []

    def _find_failure_location_tests(
        self,
        failure_locations: Sequence[str] | None,
        task_directive: str | None,
    ) -> tuple[list[str], str]:
        """Derive test files by analyzing diagnosed failure locations and task directive text."""
        candidates: list[str] = []
        if failure_locations:
            for loc in failure_locations:
                if isinstance(loc, str) and loc.strip():
                    candidates.append(loc.strip())

        if task_directive:
            # Extract filenames ending in .py mentioned in directive
            pattern = r"(?:[a-zA-Z0-9_\-\.\/]+\/)?([a-zA-Z0-9_\-]+\.py)\b"
            extracted = re.findall(pattern, task_directive)
            candidates.extend(extracted)
            full_matches = re.findall(
                r"\b(?:src\/|tests\/)[a-zA-Z0-9_\-\.\/]+\.py\b", task_directive
            )
            candidates.extend(full_matches)

        for cand in candidates:
            # Try direct mapping
            direct = self._find_direct_tests(cand)
            if direct:
                return direct, f"Failure location direct mapping from '{cand}'"
            # Try package mapping
            pkg = self._find_package_tests(cand)
            if pkg:
                return pkg, f"Failure location package mapping from '{cand}'"

        return [], ""

    def _safe_bounded_fallback(
        self,
        fallback_targets: Sequence[str] | None = None,
    ) -> tuple[tuple[str, ...], str]:
        """Apply safe bounded fallback when no specific test mapping is identified."""
        # 1. Custom fallback targets passed as argument
        if fallback_targets:
            validated: list[str] = []
            for t in fallback_targets:
                if isinstance(t, str) and t.strip():
                    try:
                        validated.append(self._validate_single_target(t.strip()))
                    except ControlledExecutionError:
                        continue
            if validated:
                unique = tuple(sorted(dict.fromkeys(validated)))[:MAX_BOUNDED_FALLBACK_COUNT]
                return (
                    unique,
                    f"Configured fallback targets selected ({len(unique)} targets)",
                )

        # 2. Selector-configured default fallback targets
        if self._default_fallback_targets:
            validated = []
            for t in self._default_fallback_targets:
                if isinstance(t, str) and t.strip():
                    try:
                        validated.append(self._validate_single_target(t.strip()))
                    except ControlledExecutionError:
                        continue
            if validated:
                unique = tuple(sorted(dict.fromkeys(validated)))[:MAX_BOUNDED_FALLBACK_COUNT]
                return (
                    unique,
                    f"Default fallback targets selected ({len(unique)} targets)",
                )

        # 3. Known repository smoke or baseline test candidates
        for cand in DEFAULT_FALLBACK_CANDIDATES:
            p = self._workspace.repository_root / cand
            if p.is_file():
                try:
                    safe_target = self._validate_single_target(cand)
                    return (
                        (safe_target,),
                        f"Safe bounded fallback: selected baseline test '{safe_target}'",
                    )
                except ControlledExecutionError:
                    continue

        # 4. First deterministically discovered unit test in repository
        tests_dir = self._workspace.repository_root / "tests"
        if tests_dir.is_dir():
            for f in sorted(tests_dir.rglob("test_*.py")):
                if f.is_file():
                    try:
                        rel = str(f.relative_to(self._workspace.repository_root)).replace(
                            "\\", "/"
                        )
                        safe_target = self._validate_single_target(rel)
                        return (
                            (safe_target,),
                            f"Safe bounded fallback: selected repository baseline '{safe_target}'",
                        )
                    except (ValueError, ControlledExecutionError):
                        continue

        # 5. Empty tuple if no tests can be identified
        return (
            (),
            "No specific test mapping found; whole-repository test execution "
            "rejected by safe bounded policy.",
        )

    def select_test_targets(
        self,
        explicit_target: str | Sequence[str] | None = None,
        affected_files: Sequence[str] | None = None,
        failure_locations: Sequence[str] | None = None,
        task_directive: str | None = None,
        fallback_targets: Sequence[str] | None = None,
    ) -> TestSelectionResult:
        """Deterministically select a bounded test scope using priority strategies.

        Priority order:
        1. EXPLICIT_TEST_TARGET
        2. DIRECT_TEST_MAPPING
        3. PACKAGE_MAPPING
        4. FAILURE_LOCATION_MAPPING
        5. SAFE_BOUNDED_FALLBACK
        """
        metadata: dict[str, Any] = {
            "explicit_target": explicit_target,
            "affected_files": list(affected_files) if affected_files else [],
            "failure_locations": list(failure_locations) if failure_locations else [],
            "task_directive": task_directive,
        }

        # -------------------------------------------------------------
        # 1. EXPLICIT_TEST_TARGET
        # -------------------------------------------------------------
        raw_explicit: list[str] = []
        if isinstance(explicit_target, str):
            trimmed = explicit_target.strip()
            if trimmed:
                # If space-separated multiple files and not a literal file with spaces
                if " " in trimmed and not (self._workspace.repository_root / trimmed).exists():
                    raw_explicit.extend(trimmed.split())
                else:
                    raw_explicit.append(trimmed)
        elif isinstance(explicit_target, (list, tuple, set)):
            for item in explicit_target:
                if isinstance(item, str) and item.strip():
                    raw_explicit.append(item.strip())

        if raw_explicit:
            validated: list[str] = [self._validate_single_target(t) for t in raw_explicit]
            unique_explicit = tuple(sorted(dict.fromkeys(validated)))
            target_spec = " ".join(unique_explicit)
            return TestSelectionResult(
                selected_tests=unique_explicit,
                strategy=TestSelectionStrategy.EXPLICIT_TEST_TARGET,
                reason=f"Explicit test target specified: {target_spec}",
                is_explicit=True,
                is_fallback=False,
                target_spec=target_spec,
                metadata=metadata,
            )

        # -------------------------------------------------------------
        # 2. DIRECT_TEST_MAPPING
        # -------------------------------------------------------------
        if affected_files:
            direct_matches: list[str] = []
            for file_path in affected_files:
                if isinstance(file_path, str) and file_path.strip():
                    direct_matches.extend(self._find_direct_tests(file_path.strip()))

            if direct_matches:
                unique_direct = tuple(sorted(dict.fromkeys(direct_matches)))[
                    :MAX_BOUNDED_TESTS
                ]
                target_spec = " ".join(unique_direct)
                return TestSelectionResult(
                    selected_tests=unique_direct,
                    strategy=TestSelectionStrategy.DIRECT_TEST_MAPPING,
                    reason=f"Direct source-to-test mapping ({len(unique_direct)} targets)",
                    is_explicit=False,
                    is_fallback=False,
                    target_spec=target_spec,
                    metadata=metadata,
                )

        # -------------------------------------------------------------
        # 3. PACKAGE_MAPPING
        # -------------------------------------------------------------
        if affected_files:
            pkg_matches: list[str] = []
            for file_path in affected_files:
                if isinstance(file_path, str) and file_path.strip():
                    pkg_matches.extend(self._find_package_tests(file_path.strip()))

            if pkg_matches:
                unique_pkg = tuple(sorted(dict.fromkeys(pkg_matches)))[:MAX_BOUNDED_TESTS]
                target_spec = " ".join(unique_pkg)
                return TestSelectionResult(
                    selected_tests=unique_pkg,
                    strategy=TestSelectionStrategy.PACKAGE_MAPPING,
                    reason=f"Package domain test mapping ({len(unique_pkg)} targets)",
                    is_explicit=False,
                    is_fallback=False,
                    target_spec=target_spec,
                    metadata=metadata,
                )

        # -------------------------------------------------------------
        # 4. FAILURE_LOCATION_MAPPING
        # -------------------------------------------------------------
        if failure_locations or task_directive:
            fail_tests, fail_reason = self._find_failure_location_tests(
                failure_locations=failure_locations,
                task_directive=task_directive,
            )
            if fail_tests:
                unique_fail = tuple(sorted(dict.fromkeys(fail_tests)))[:MAX_BOUNDED_TESTS]
                target_spec = " ".join(unique_fail)
                return TestSelectionResult(
                    selected_tests=unique_fail,
                    strategy=TestSelectionStrategy.FAILURE_LOCATION_MAPPING,
                    reason=f"{fail_reason} ({len(unique_fail)} targets)",
                    is_explicit=False,
                    is_fallback=False,
                    target_spec=target_spec,
                    metadata=metadata,
                )

        # -------------------------------------------------------------
        # 5. SAFE_BOUNDED_FALLBACK
        # -------------------------------------------------------------
        fallback_tests, fallback_reason = self._safe_bounded_fallback(
            fallback_targets=fallback_targets
        )
        target_spec = " ".join(fallback_tests)
        return TestSelectionResult(
            selected_tests=fallback_tests,
            strategy=TestSelectionStrategy.SAFE_BOUNDED_FALLBACK,
            reason=fallback_reason,
            is_explicit=False,
            is_fallback=True,
            target_spec=target_spec,
            metadata=metadata,
        )
