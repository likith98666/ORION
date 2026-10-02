from uuid import uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.permissions import AgentPermission
from orion.core.planning.validator import PlanValidator
from orion.core.swe.graph import SWETaskGraph
from orion.core.swe.stages import (
    SWETaskStage,
)


def test_swe_task_graph_creates_all_seven_stages():
    """Verify all 7 canonical SWE stages are present in the task graph."""
    task_id = uuid4()
    graph = SWETaskGraph.create(task_id=task_id, objective="Fix regression bug")

    assert len(graph.steps) == 7
    expected_stages = [
        SWETaskStage.INSPECT_REPOSITORY,
        SWETaskStage.ANALYZE_FAILURE,
        SWETaskStage.FORMULATE_FIX,
        SWETaskStage.IMPLEMENT_CHANGE,
        SWETaskStage.RUN_TESTS,
        SWETaskStage.VERIFY,
        SWETaskStage.GENERATE_REPORT,
    ]

    for idx, expected_stage in enumerate(expected_stages, start=1):
        step = graph.steps[idx - 1]
        assert step.order == idx
        assert graph.get_stage(step.id) == expected_stage
        assert graph.get_step(expected_stage).id == step.id


def test_swe_task_graph_enforces_strict_dependencies():
    """Verify each stage strictly depends on its immediate predecessor."""
    task_id = uuid4()
    graph = SWETaskGraph.create(task_id=task_id)

    # Step 1 (INSPECT_REPOSITORY) has no dependencies
    step1 = graph.steps[0]
    assert step1.dependencies == frozenset()

    # Steps 2 to 7 each depend on the previous step
    for i in range(1, 7):
        current_step = graph.steps[i]
        prev_step = graph.steps[i - 1]
        assert current_step.dependencies == frozenset({prev_step.id})


def test_swe_task_graph_passes_plan_validator():
    """Verify the constructed graph validates cleanly through ORION's PlanValidator."""
    task_id = uuid4()
    graph = SWETaskGraph.create(task_id=task_id)

    validator = PlanValidator()
    result = validator.validate(list(graph.steps))

    assert result.valid is True
    assert result.errors == ()


def test_swe_task_graph_deterministic_ordering():
    """Verify graph creation is deterministic across multiple calls."""
    task_id = uuid4()
    graph1 = SWETaskGraph.create(task_id=task_id)
    graph2 = SWETaskGraph.create(task_id=task_id)

    assert len(graph1.steps) == len(graph2.steps) == 7
    for s1, s2 in zip(graph1.steps, graph2.steps, strict=False):
        assert s1.order == s2.order
        assert graph1.get_stage(s1.id) == graph2.get_stage(s2.id)


def test_swe_task_graph_creates_matching_agent_tasks():
    """Verify create_agent_tasks produces valid AgentTask instances with required capabilities."""
    task_id = uuid4()
    graph = SWETaskGraph.create(task_id=task_id)

    agent_tasks = graph.create_agent_tasks()
    assert len(agent_tasks) == 7

    inspect_task = agent_tasks[0]
    assert inspect_task.required_capability == AgentCapability.REPOSITORY_ANALYSIS
    assert AgentPermission.READ_FILES in inspect_task.required_permissions

    analyze_task = agent_tasks[1]
    assert analyze_task.required_capability == AgentCapability.SOFTWARE_DEBUGGING
    assert AgentPermission.CODE_EXECUTION in analyze_task.required_permissions

    formulate_task = agent_tasks[2]
    assert formulate_task.required_capability == AgentCapability.REASONING

    implement_task = agent_tasks[3]
    assert implement_task.required_capability == AgentCapability.CODE_MODIFICATION
    assert AgentPermission.WRITE_FILES in implement_task.required_permissions

    test_task = agent_tasks[4]
    assert test_task.required_capability == AgentCapability.TESTING
    assert AgentPermission.CODE_EXECUTION in test_task.required_permissions

    verify_task = agent_tasks[5]
    assert verify_task.required_capability == AgentCapability.VERIFICATION

    report_task = agent_tasks[6]
    assert report_task.required_capability == AgentCapability.WRITING


def test_swe_task_graph_spec_retrieval():
    """Verify stage specifications can be retrieved accurately."""
    task_id = uuid4()
    graph = SWETaskGraph.create(task_id=task_id)

    spec = graph.get_spec(SWETaskStage.INSPECT_REPOSITORY)
    assert spec.stage == SWETaskStage.INSPECT_REPOSITORY
    assert spec.allows_file_modification is False
    assert "list_files" in spec.allowed_tools

    implement_spec = graph.get_spec(SWETaskStage.IMPLEMENT_CHANGE)
    assert implement_spec.allows_file_modification is True
    assert "write_file" in implement_spec.allowed_tools
