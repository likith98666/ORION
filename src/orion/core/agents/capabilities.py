from enum import Enum


class AgentCapability(str, Enum):
    """Capabilities that an ORION agent can possess."""

    RESEARCH = "research"
    WEB_SEARCH = "web_search"
    DATA_ANALYSIS = "data_analysis"
    CODE_EXECUTION = "code_execution"
    FILE_PROCESSING = "file_processing"
    DOCUMENT_GENERATION = "document_generation"
    DATABASE_QUERY = "database_query"
    REASONING = "reasoning"
    WRITING = "writing"
    VERIFICATION = "verification"
    REPOSITORY_ANALYSIS = "repository_analysis"
    SOFTWARE_DEBUGGING = "software_debugging"
    CODE_MODIFICATION = "code_modification"
    TESTING = "testing"
