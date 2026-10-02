from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from orion.core.swe.errors import UnverifiedSuccessError
from orion.core.swe.stages import SWETaskStage

if TYPE_CHECKING:
    from orion.core.swe.evaluation import MissionEvaluation

MAX_EVIDENCE_CONTENT_LENGTH = 16384  # 16 KB bounded
MAX_EVIDENCE_SUMMARY_LENGTH = 500
MAX_METADATA_STRING_LENGTH = 4096

SENSITIVE_KEY_PATTERNS = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "access_key",
    "authorization",
    "auth",
    "credential",
    "bearer",
    "cert",
    "private",
})


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize metadata to redact sensitive keys and bound large string values."""
    if not metadata:
        return {}

    sanitized: dict[str, Any] = {}
    for key, val in metadata.items():
        key_str = str(key)
        if any(pattern in key_str.lower() for pattern in SENSITIVE_KEY_PATTERNS):
            sanitized[key_str] = "[REDACTED]"
        elif isinstance(val, str):
            if len(val) > MAX_METADATA_STRING_LENGTH:
                sanitized[key_str] = val[:MAX_METADATA_STRING_LENGTH] + "... [TRUNCATED]"
            else:
                sanitized[key_str] = val
        elif isinstance(val, dict):
            sanitized[key_str] = _sanitize_metadata(val)
        elif isinstance(val, (list, tuple)):
            cleaned_list: list[Any] = []
            for item in val:
                if isinstance(item, str) and len(item) > MAX_METADATA_STRING_LENGTH:
                    cleaned_list.append(item[:MAX_METADATA_STRING_LENGTH] + "... [TRUNCATED]")
                elif isinstance(item, dict):
                    cleaned_list.append(_sanitize_metadata(item))
                else:
                    cleaned_list.append(item)
            sanitized[key_str] = type(val)(cleaned_list)
        else:
            sanitized[key_str] = val

    return sanitized


class EvidenceLevel(str, Enum):
    """Factual hierarchy level of evidence collected during an SWE workflow."""

    CLAIMED = "claimed"
    OBSERVED = "observed"
    VERIFIED = "verified"


class EvidenceCategory(str, Enum):
    """Controlled taxonomy of evidence types recorded during an SWE workflow."""

    REPOSITORY_STATE = "repository_state"
    FILE_OBSERVATION = "file_observation"
    DIAGNOSTIC_RESULT = "diagnostic_result"
    PROPOSED_CHANGE = "proposed_change"
    FILE_CHANGE = "file_change"
    COMMAND_RESULT = "command_result"
    TEST_RESULT = "test_result"
    DIFF_RESULT = "diff_result"
    VERIFICATION_RESULT = "verification_result"
    RECOVERY_EVENT = "recovery_event"
    MISSION_OUTCOME = "mission_outcome"


@dataclass(frozen=True)
class EvidenceItem:
    """An individual atomic item of evidence recorded in the workflow with full provenance."""

    id: UUID
    level: EvidenceLevel
    category: EvidenceCategory
    stage: SWETaskStage
    source: str
    content: str
    summary: str = ""
    task_id: UUID | None = None
    execution_id: UUID | None = None
    tool_name: str | None = None
    request_id: UUID | None = None
    trace_id: UUID | None = None
    workspace_root: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.level, EvidenceLevel):
            raise TypeError("level must be an EvidenceLevel instance.")
        if not isinstance(self.category, EvidenceCategory):
            raise TypeError("category must be an EvidenceCategory instance.")
        if not isinstance(self.stage, SWETaskStage):
            raise TypeError("stage must be an SWETaskStage instance.")
        if not self.source or not self.source.strip():
            raise ValueError("source cannot be empty.")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty.")

        # Bound content length to prevent unbounded memory growth
        if len(self.content) > MAX_EVIDENCE_CONTENT_LENGTH:
            orig_len = len(self.content)
            bounded = self.content[:MAX_EVIDENCE_CONTENT_LENGTH] + "\n... [TRUNCATED]"
            object.__setattr__(self, "content", bounded)
            new_metadata = dict(self.metadata)
            new_metadata["content_truncated"] = True
            new_metadata["original_length"] = orig_len
            object.__setattr__(self, "metadata", new_metadata)

        # Default summary from content if not provided
        if not self.summary or not self.summary.strip():
            first_line = self.content.splitlines()[0] if self.content else ""
            summary_candidate = first_line[:MAX_EVIDENCE_SUMMARY_LENGTH].strip()
            object.__setattr__(self, "summary", summary_candidate or f"{self.category.value} evidence")
        elif len(self.summary) > MAX_EVIDENCE_SUMMARY_LENGTH:
            object.__setattr__(self, "summary", self.summary[:MAX_EVIDENCE_SUMMARY_LENGTH] + "...")

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence item to serializable dictionary representation with full provenance."""
        return {
            "id": str(self.id),
            "level": self.level.value,
            "category": self.category.value,
            "stage": self.stage.value,
            "source": self.source,
            "content": self.content,
            "summary": self.summary,
            "task_id": str(self.task_id) if self.task_id else None,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "tool_name": self.tool_name,
            "request_id": str(self.request_id) if self.request_id else None,
            "trace_id": str(self.trace_id) if self.trace_id else None,
            "workspace_root": self.workspace_root,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        """Reconstruct evidence item from dictionary representation."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary.")

        raw_ts = data.get("timestamp")
        if isinstance(raw_ts, str):
            ts = datetime.fromisoformat(raw_ts)
        elif isinstance(raw_ts, datetime):
            ts = raw_ts
        else:
            ts = datetime.now(UTC)

        return cls(
            id=UUID(str(data["id"])),
            level=EvidenceLevel(str(data["level"])),
            category=EvidenceCategory(str(data["category"])),
            stage=SWETaskStage(str(data["stage"])),
            source=str(data["source"]),
            content=str(data["content"]),
            summary=str(data.get("summary", "")),
            task_id=UUID(str(data["task_id"])) if data.get("task_id") else None,
            execution_id=UUID(str(data["execution_id"])) if data.get("execution_id") else None,
            tool_name=str(data["tool_name"]) if data.get("tool_name") else None,
            request_id=UUID(str(data["request_id"])) if data.get("request_id") else None,
            trace_id=UUID(str(data["trace_id"])) if data.get("trace_id") else None,
            workspace_root=str(data["workspace_root"]) if data.get("workspace_root") else None,
            metadata=dict(data.get("metadata", {})),
            timestamp=ts,
        )


class EvidenceLedger:
    """Thread-safe append-only ledger for all evidence collected during an SWE mission."""

    def __init__(self) -> None:
        self._items: list[EvidenceItem] = []

    def record(
        self,
        level: EvidenceLevel,
        stage: SWETaskStage,
        source: str,
        content: str,
        category: EvidenceCategory | None = None,
        summary: str = "",
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_name: str | None = None,
        request_id: UUID | None = None,
        trace_id: UUID | None = None,
        workspace_root: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Record a single evidence entry into the ledger with full provenance and sanitized metadata."""
        if category is None:
            if level == EvidenceLevel.VERIFIED:
                category = EvidenceCategory.VERIFICATION_RESULT
            elif level == EvidenceLevel.CLAIMED:
                category = (
                    EvidenceCategory.PROPOSED_CHANGE
                    if stage == SWETaskStage.FORMULATE_FIX
                    else EvidenceCategory.DIAGNOSTIC_RESULT
                )
            else:
                category = EvidenceCategory.COMMAND_RESULT

        clean_metadata = _sanitize_metadata(metadata)

        item = EvidenceItem(
            id=uuid4(),
            level=level,
            category=category,
            stage=stage,
            source=source.strip(),
            content=content.strip(),
            summary=summary.strip(),
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            request_id=request_id,
            trace_id=trace_id,
            workspace_root=workspace_root,
            metadata=clean_metadata,
            timestamp=datetime.now(UTC),
        )
        self._items.append(item)
        return item

    def record_claimed(
        self,
        stage: SWETaskStage,
        source: str,
        content: str,
        category: EvidenceCategory | None = None,
        summary: str = "",
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_name: str | None = None,
        request_id: UUID | None = None,
        trace_id: UUID | None = None,
        workspace_root: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Record an agent-asserted hypothesis or claim."""
        effective_category = category or (
            EvidenceCategory.PROPOSED_CHANGE
            if stage == SWETaskStage.FORMULATE_FIX
            else EvidenceCategory.DIAGNOSTIC_RESULT
        )
        return self.record(
            level=EvidenceLevel.CLAIMED,
            stage=stage,
            source=source,
            content=content,
            category=effective_category,
            summary=summary,
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            request_id=request_id,
            trace_id=trace_id,
            workspace_root=workspace_root,
            metadata=metadata,
        )

    def record_observed(
        self,
        stage: SWETaskStage,
        source: str,
        content: str,
        category: EvidenceCategory | None = None,
        summary: str = "",
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_name: str | None = None,
        request_id: UUID | None = None,
        trace_id: UUID | None = None,
        workspace_root: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Record a tangible runtime observation (e.g. tool execution output, file diff)."""
        effective_category = category or EvidenceCategory.COMMAND_RESULT
        return self.record(
            level=EvidenceLevel.OBSERVED,
            stage=stage,
            source=source,
            content=content,
            category=effective_category,
            summary=summary,
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            request_id=request_id,
            trace_id=trace_id,
            workspace_root=workspace_root,
            metadata=metadata,
        )

    def record_verified(
        self,
        stage: SWETaskStage,
        source: str,
        content: str,
        category: EvidenceCategory | None = None,
        summary: str = "",
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_name: str | None = None,
        request_id: UUID | None = None,
        trace_id: UUID | None = None,
        workspace_root: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Record an outcome that has passed formal verification via VerificationEngine."""
        effective_category = category or EvidenceCategory.VERIFICATION_RESULT
        return self.record(
            level=EvidenceLevel.VERIFIED,
            stage=stage,
            source=source,
            content=content,
            category=effective_category,
            summary=summary,
            task_id=task_id,
            execution_id=execution_id,
            tool_name=tool_name,
            request_id=request_id,
            trace_id=trace_id,
            workspace_root=workspace_root,
            metadata=metadata,
        )

    def get_items(
        self,
        level: EvidenceLevel | None = None,
        stage: SWETaskStage | None = None,
        category: EvidenceCategory | None = None,
        execution_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> tuple[EvidenceItem, ...]:
        """Query items with filtering by level, stage, category, execution, or task."""
        results = self._items
        if level is not None:
            results = [item for item in results if item.level == level]
        if stage is not None:
            results = [item for item in results if item.stage == stage]
        if category is not None:
            results = [item for item in results if item.category == category]
        if execution_id is not None:
            results = [item for item in results if item.execution_id == execution_id]
        if task_id is not None:
            results = [item for item in results if item.task_id == task_id]
        return tuple(results)

    def has_verified(self, stage: SWETaskStage | None = None) -> bool:
        """Return True if any VERIFIED evidence exists."""
        return bool(self.get_items(level=EvidenceLevel.VERIFIED, stage=stage))

    def has_observed(self, stage: SWETaskStage | None = None) -> bool:
        """Return True if any OBSERVED evidence exists."""
        return bool(self.get_items(level=EvidenceLevel.OBSERVED, stage=stage))

    def has_claimed(self, stage: SWETaskStage | None = None) -> bool:
        """Return True if any CLAIMED evidence exists."""
        return bool(self.get_items(level=EvidenceLevel.CLAIMED, stage=stage))

    def clear(self) -> None:
        """Clear ledger contents."""
        self._items.clear()


@dataclass(frozen=True)
class SWEReport:
    """Structured mission result generated at the conclusion of an SWE task."""

    mission_id: UUID
    task_id: UUID
    workspace_root: str
    status: str
    claimed_evidence: tuple[EvidenceItem, ...]
    observed_evidence: tuple[EvidenceItem, ...]
    verified_evidence: tuple[EvidenceItem, ...]
    evaluation: MissionEvaluation | None = None
    stages_completed: tuple[SWETaskStage, ...] = ()
    files_modified: tuple[str, ...] = ()
    summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, UUID):
            raise TypeError("mission_id must be a UUID.")
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID.")
        if not self.workspace_root or not self.workspace_root.strip():
            raise ValueError("workspace_root cannot be empty.")
        if not self.status or not self.status.strip():
            raise ValueError("status cannot be empty.")

        # Invariant 1: cannot claim verified_success without VERIFIED evidence
        if self.status == "verified_success" and not self.verified_evidence:
            raise UnverifiedSuccessError(
                "Cannot mark SWE report as 'verified_success' without VERIFIED evidence. "
                "Tool execution or observations alone do not constitute verification."
            )

        # Invariant 2: cannot claim verified_success if evaluation status is not PASS
        if self.evaluation is not None and self.status == "verified_success":
            from orion.core.swe.evaluation import EvaluationStatus
            if self.evaluation.status != EvaluationStatus.PASS:
                raise UnverifiedSuccessError(
                    f"Cannot mark SWE report as 'verified_success' when evaluation status is '{self.evaluation.status.value}'. "
                    "All evaluation criteria must pass for verified success."
                )

    @classmethod
    def create(
        cls,
        mission_id: UUID,
        task_id: UUID,
        workspace_root: str,
        ledger: EvidenceLedger,
        status: str,
        evaluation: MissionEvaluation | None = None,
        stages_completed: tuple[SWETaskStage, ...] = (),
        files_modified: tuple[str, ...] = (),
        summary: str = "",
    ) -> SWEReport:
        """Build an SWEReport directly from an EvidenceLedger and evaluation result."""
        claimed = ledger.get_items(level=EvidenceLevel.CLAIMED)
        observed = ledger.get_items(level=EvidenceLevel.OBSERVED)
        verified = ledger.get_items(level=EvidenceLevel.VERIFIED)

        return cls(
            mission_id=mission_id,
            task_id=task_id,
            workspace_root=workspace_root,
            status=status,
            claimed_evidence=claimed,
            observed_evidence=observed,
            verified_evidence=verified,
            evaluation=evaluation,
            stages_completed=stages_completed,
            files_modified=files_modified,
            summary=summary,
        )

    @property
    def is_verified_success(self) -> bool:
        """Return True if mission completed with verified success and passing evaluation."""
        from orion.core.swe.evaluation import EvaluationStatus
        return (
            self.status == "verified_success"
            and len(self.verified_evidence) > 0
            and (self.evaluation is None or self.evaluation.status == EvaluationStatus.PASS)
        )

    @property
    def total_evidence_count(self) -> int:
        """Return total count of evidence items across all levels."""
        return len(self.claimed_evidence) + len(self.observed_evidence) + len(self.verified_evidence)

    def get_evidence_by_category(self, category: EvidenceCategory) -> tuple[EvidenceItem, ...]:
        """Return all evidence items across levels matching a specific category."""
        all_items = self.claimed_evidence + self.observed_evidence + self.verified_evidence
        return tuple(item for item in all_items if item.category == category)

    def get_evidence_by_stage(self, stage: SWETaskStage) -> tuple[EvidenceItem, ...]:
        """Return all evidence items across levels produced during a specific stage."""
        all_items = self.claimed_evidence + self.observed_evidence + self.verified_evidence
        return tuple(item for item in all_items if item.stage == stage)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to a concise, structured dictionary representation."""
        test_passed_cnt = self.evaluation.metrics.tests_passed if self.evaluation else sum(
            1 for item in self.observed_evidence
            if item.category == EvidenceCategory.TEST_RESULT
            and (item.metadata.get("exit_code") == 0 or item.metadata.get("status") == "passed")
        )
        test_failed_cnt = self.evaluation.metrics.tests_failed if self.evaluation else sum(
            1 for item in self.observed_evidence
            if item.category == EvidenceCategory.TEST_RESULT
            and (item.metadata.get("exit_code") not in (0, None) or item.metadata.get("status") == "failed")
        )
        verif_passed_cnt = self.evaluation.metrics.verification_passed if self.evaluation else len(self.verified_evidence)
        verif_failed_cnt = self.evaluation.metrics.verification_failed if self.evaluation else sum(
            1 for item in self.observed_evidence
            if item.category == EvidenceCategory.VERIFICATION_RESULT and "FAILED" in item.content
        )
        recovery_attempts_cnt = self.evaluation.metrics.recovery_attempts if self.evaluation else sum(
            1 for item in self.observed_evidence if item.category == EvidenceCategory.RECOVERY_EVENT
        )

        return {
            "mission": {
                "mission_id": str(self.mission_id),
                "task_id": str(self.task_id),
                "status": self.status,
                "summary": self.summary,
                "created_at": self.created_at.isoformat(),
            },
            "workspace": {
                "workspace_root": self.workspace_root,
            },
            "stages": {
                "completed": [s.value for s in self.stages_completed],
                "total_completed": len(self.stages_completed),
            },
            "changes": {
                "files_modified": list(self.files_modified),
                "total_files_modified": len(self.files_modified),
            },
            "tests": {
                "tests_passed": test_passed_cnt,
                "tests_failed": test_failed_cnt,
                "outcome": self.evaluation.criteria.test_passed if self.evaluation else (test_passed_cnt > 0 and test_failed_cnt == 0),
            },
            "verification": {
                "verification_passed": verif_passed_cnt,
                "verification_failed": verif_failed_cnt,
                "outcome": self.evaluation.criteria.verification_passed if self.evaluation else (verif_passed_cnt > 0),
                "verified_evidence_count": len(self.verified_evidence),
            },
            "recovery": {
                "recovery_attempts": recovery_attempts_cnt,
                "recovery_transparent": self.evaluation.criteria.recovery_transparent if self.evaluation else True,
            },
            "evidence_summary": {
                "claimed_count": len(self.claimed_evidence),
                "observed_count": len(self.observed_evidence),
                "verified_count": len(self.verified_evidence),
                "total_items": self.total_evidence_count,
            },
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "final_outcome": self.status,
        }
