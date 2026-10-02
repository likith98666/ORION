from dataclasses import dataclass
from enum import Enum

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.permissions import AgentPermission


class SWETaskStage(str, Enum):
    """The 7 canonical stages of the Autonomous Software Engineering task graph."""

    INSPECT_REPOSITORY = "inspect_repository"
    ANALYZE_FAILURE = "analyze_failure"
    FORMULATE_FIX = "formulate_fix"
    IMPLEMENT_CHANGE = "implement_change"
    RUN_TESTS = "run_tests"
    VERIFY = "verify"
    GENERATE_REPORT = "generate_report"


@dataclass(frozen=True)
class SWEStepSpec:
    """Specification of constraints, capabilities, and permissions for an SWE stage."""

    stage: SWETaskStage
    order: int
    name: str
    description: str
    required_capability: AgentCapability
    required_permissions: frozenset[AgentPermission]
    allowed_tools: frozenset[str]
    allows_file_modification: bool
    expected_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.stage, SWETaskStage):
            raise TypeError("stage must be an SWETaskStage instance.")
        if self.order < 1 or self.order > 7:
            raise ValueError("order must be between 1 and 7.")
        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty.")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty.")
        if not isinstance(self.required_capability, AgentCapability):
            raise TypeError("required_capability must be an AgentCapability.")
        if not isinstance(self.required_permissions, (frozenset, set)):
            raise TypeError("required_permissions must be a frozenset.")
        if not isinstance(self.allowed_tools, (frozenset, set)):
            raise TypeError("allowed_tools must be a frozenset.")
        if not isinstance(self.allows_file_modification, bool):
            raise TypeError("allows_file_modification must be a boolean.")


FILE_MODIFICATION_TOOLS: frozenset[str] = frozenset({
    "write_file",
    "apply_change",
})

DEFAULT_SWE_STAGE_SPECS: dict[SWETaskStage, SWEStepSpec] = {
    SWETaskStage.INSPECT_REPOSITORY: SWEStepSpec(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        order=1,
        name="Inspect Repository",
        description=(
            "Establish repository structure, directory layout, and relevant source/test context. "
            "Read-only inspection; must not modify any files."
        ),
        required_capability=AgentCapability.REPOSITORY_ANALYSIS,
        required_permissions=frozenset({AgentPermission.READ_FILES}),
        allowed_tools=frozenset({"list_files", "read_file", "search_files", "diff"}),
        allows_file_modification=False,
        expected_requirements=("repository structure",),
    ),
    SWETaskStage.ANALYZE_FAILURE: SWEStepSpec(
        stage=SWETaskStage.ANALYZE_FAILURE,
        order=2,
        name="Analyze Failure",
        description=(
            "Understand the reported problem, reproduce via test execution, and identify root cause. "
            "Produce structured diagnostic reasoning and evidence."
        ),
        required_capability=AgentCapability.SOFTWARE_DEBUGGING,
        required_permissions=frozenset({
            AgentPermission.READ_FILES,
            AgentPermission.CODE_EXECUTION,
        }),
        allowed_tools=frozenset({"read_file", "search_files", "run_tests", "diff"}),
        allows_file_modification=False,
        expected_requirements=("failure diagnosis", "evidence"),
    ),
    SWETaskStage.FORMULATE_FIX: SWEStepSpec(
        stage=SWETaskStage.FORMULATE_FIX,
        order=3,
        name="Formulate Fix",
        description=(
            "Produce a concrete proposed change plan identifying target files, intended modifications, "
            "expected behavior, validation strategy, and constraints. Must not modify files."
        ),
        required_capability=AgentCapability.REASONING,
        required_permissions=frozenset({AgentPermission.READ_FILES}),
        allowed_tools=frozenset({"read_file", "search_files"}),
        allows_file_modification=False,
        expected_requirements=(
            "target files",
            "intended modification",
            "expected behavior",
            "validation strategy",
            "constraints",
        ),
    ),
    SWETaskStage.IMPLEMENT_CHANGE: SWEStepSpec(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        order=4,
        name="Implement Change",
        description=(
            "Apply controlled modifications according to the formulated plan. High-risk file "
            "writes require authorization and approval."
        ),
        required_capability=AgentCapability.CODE_MODIFICATION,
        required_permissions=frozenset({
            AgentPermission.WRITE_FILES,
            AgentPermission.READ_FILES,
        }),
        allowed_tools=frozenset({"write_file", "apply_change", "diff"}),
        allows_file_modification=True,
        expected_requirements=("change applied",),
    ),
    SWETaskStage.RUN_TESTS: SWEStepSpec(
        stage=SWETaskStage.RUN_TESTS,
        order=5,
        name="Run Tests",
        description=(
            "Execute allowlisted test suites to validate changes. No arbitrary command execution."
        ),
        required_capability=AgentCapability.TESTING,
        required_permissions=frozenset({AgentPermission.CODE_EXECUTION}),
        allowed_tools=frozenset({"run_tests"}),
        allows_file_modification=False,
        expected_requirements=("test execution results",),
    ),
    SWETaskStage.VERIFY: SWEStepSpec(
        stage=SWETaskStage.VERIFY,
        order=6,
        name="Verify",
        description=(
            "Formally verify test results and repository state using VerificationEngine. "
            "Determine whether the requested outcome was actually achieved."
        ),
        required_capability=AgentCapability.VERIFICATION,
        required_permissions=frozenset(),
        allowed_tools=frozenset(),
        allows_file_modification=False,
        expected_requirements=("verification passed",),
    ),
    SWETaskStage.GENERATE_REPORT: SWEStepSpec(
        stage=SWETaskStage.GENERATE_REPORT,
        order=7,
        name="Generate Report",
        description=(
            "Produce structured mission result distinguishing CLAIMED, OBSERVED, and VERIFIED evidence. "
            "Final success requires VERIFIED evidence."
        ),
        required_capability=AgentCapability.WRITING,
        required_permissions=frozenset(),
        allowed_tools=frozenset(),
        allows_file_modification=False,
        expected_requirements=("mission report",),
    ),
}
