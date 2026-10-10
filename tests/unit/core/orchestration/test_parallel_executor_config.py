from orion.core.orchestration.parallel_executor import ParallelExecutor


def test_parallel_executor_has_safe_default_worker_limit():
    executor = ParallelExecutor(execution_coordinator=None)

    assert executor.max_workers == 4
