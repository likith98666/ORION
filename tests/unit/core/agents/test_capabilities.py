from orion.core.agents.capabilities import AgentCapability


def test_agent_capabilities_exist() -> None:
    assert AgentCapability.RESEARCH.value == "research"
    assert AgentCapability.WEB_SEARCH.value == "web_search"
    assert AgentCapability.DATA_ANALYSIS.value == "data_analysis"
    assert AgentCapability.CODE_EXECUTION.value == "code_execution"
    assert AgentCapability.FILE_PROCESSING.value == "file_processing"
    assert AgentCapability.DOCUMENT_GENERATION.value == "document_generation"
    assert AgentCapability.DATABASE_QUERY.value == "database_query"
    assert AgentCapability.REASONING.value == "reasoning"
    assert AgentCapability.WRITING.value == "writing"
    assert AgentCapability.VERIFICATION.value == "verification"


def test_agent_capability_is_string_compatible() -> None:
    assert AgentCapability.RESEARCH == "research"


def test_all_agent_capabilities_are_unique() -> None:
    values = [capability.value for capability in AgentCapability]

    assert len(values) == len(set(values))
