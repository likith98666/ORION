from orion.core.agents.permissions import AgentPermission


def test_agent_permissions_exist() -> None:
    assert AgentPermission.READ_FILES.value == "read_files"
    assert AgentPermission.WRITE_FILES.value == "write_files"
    assert AgentPermission.WEB_ACCESS.value == "web_access"
    assert AgentPermission.CODE_EXECUTION.value == "code_execution"
    assert AgentPermission.DATABASE_READ.value == "database_read"
    assert AgentPermission.DATABASE_WRITE.value == "database_write"
    assert AgentPermission.EXTERNAL_API.value == "external_api"
    assert AgentPermission.SEND_MESSAGES.value == "send_messages"


def test_agent_permission_is_string_compatible() -> None:
    assert AgentPermission.WEB_ACCESS == "web_access"


def test_all_agent_permissions_are_unique() -> None:
    values = [permission.value for permission in AgentPermission]

    assert len(values) == len(set(values))