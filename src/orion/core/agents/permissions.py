from enum import Enum


class AgentPermission(str, Enum):
    """Permissions that control what an ORION agent may access."""

    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    WEB_ACCESS = "web_access"
    CODE_EXECUTION = "code_execution"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    EXTERNAL_API = "external_api"
    SEND_MESSAGES = "send_messages"
