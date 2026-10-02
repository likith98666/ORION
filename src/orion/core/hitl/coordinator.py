"""Thread-safe coordinator for Human-in-the-Loop oversight, interventions, and clarifications."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from orion.core.hitl.models import (
    ClarificationRequest,
    ClarificationStatus,
    HumanIntervention,
    InterventionType,
    OperatorFeedback,
)


class HITLCoordinator:
    """Central authority managing human interventions, interactive clarifications, and feedback."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._clarifications: dict[UUID, ClarificationRequest] = {}
        self._interventions: dict[UUID, list[HumanIntervention]] = {}
        self._feedback: dict[UUID, list[OperatorFeedback]] = {}
        self._paused_missions: set[UUID] = set()
        self._steering_queues: dict[UUID, list[str]] = {}

    def request_clarification(
        self,
        mission_id: UUID,
        task_id: UUID,
        question: str,
        context: str,
        options: Sequence[str] = (),
        default_choice: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> ClarificationRequest:
        """Issue an interactive clarification request when ambiguity is detected."""
        req_id = uuid4()
        req = ClarificationRequest(
            request_id=req_id,
            mission_id=mission_id,
            task_id=task_id,
            question=question,
            context=context,
            options=tuple(options),
            default_choice=default_choice,
            timeout_seconds=timeout_seconds,
            status=ClarificationStatus.PENDING,
        )
        with self._lock:
            self._clarifications[req_id] = req
        return req

    def respond_clarification(
        self,
        request_id: UUID,
        response_text: str,
        operator: str,
    ) -> ClarificationRequest:
        """Resolve a pending clarification with operator guidance."""
        with self._lock:
            existing = self._clarifications.get(request_id)
            if not existing:
                raise KeyError(f"Clarification request '{request_id}' not found.")
            if existing.status != ClarificationStatus.PENDING:
                raise ValueError(
                    f"Clarification '{request_id}' is already {existing.status.value}."
                )

            resolved = ClarificationRequest(
                request_id=existing.request_id,
                mission_id=existing.mission_id,
                task_id=existing.task_id,
                question=existing.question,
                context=existing.context,
                options=existing.options,
                default_choice=existing.default_choice,
                timeout_seconds=existing.timeout_seconds,
                status=ClarificationStatus.ANSWERED,
                response=response_text.strip(),
                answered_by=operator.strip(),
                answered_at=datetime.now(UTC).isoformat(),
                created_at=existing.created_at,
            )
            self._clarifications[request_id] = resolved

            # Also record resolved guidance as steering context
            self._enqueue_steering(
                existing.mission_id,
                f"Operator Clarification [{existing.question}]: {response_text.strip()}",
            )

            return resolved

    def record_intervention(
        self,
        mission_id: UUID,
        intervention_type: InterventionType,
        operator: str,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> HumanIntervention:
        """Log an explicit human operator action and update workflow control state."""
        interv_id = uuid4()
        interv = HumanIntervention(
            intervention_id=interv_id,
            mission_id=mission_id,
            intervention_type=intervention_type,
            operator=operator,
            reason=reason,
            payload=payload or {},
            applied=True,
        )

        with self._lock:
            if intervention_type == InterventionType.PAUSE:
                self._paused_missions.add(mission_id)
            elif intervention_type == InterventionType.RESUME:
                self._paused_missions.discard(mission_id)
            elif intervention_type == InterventionType.STEER:
                instruction = str((payload or {}).get("instruction", reason))
                self._enqueue_steering(mission_id, instruction)

            if mission_id not in self._interventions:
                self._interventions[mission_id] = []
            self._interventions[mission_id].append(interv)

        return interv

    def pause_mission(self, mission_id: UUID, operator: str, reason: str) -> HumanIntervention:
        """Pause a mission safely at the current stage boundary."""
        return self.record_intervention(
            mission_id=mission_id,
            intervention_type=InterventionType.PAUSE,
            operator=operator,
            reason=reason,
        )

    def resume_mission(self, mission_id: UUID, operator: str, reason: str) -> HumanIntervention:
        """Resume a paused mission."""
        return self.record_intervention(
            mission_id=mission_id,
            intervention_type=InterventionType.RESUME,
            operator=operator,
            reason=reason,
        )

    def steer_mission(
        self, mission_id: UUID, instruction: str, operator: str, reason: str = ""
    ) -> HumanIntervention:
        """Inject operator guidance into the execution context."""
        return self.record_intervention(
            mission_id=mission_id,
            intervention_type=InterventionType.STEER,
            operator=operator,
            reason=reason or instruction,
            payload={"instruction": instruction},
        )

    def force_fail_mission(
        self, mission_id: UUID, operator: str, reason: str
    ) -> HumanIntervention:
        """Operator terminates mission with explicit rationale."""
        return self.record_intervention(
            mission_id=mission_id,
            intervention_type=InterventionType.FORCE_FAIL,
            operator=operator,
            reason=reason,
        )

    def is_mission_paused(self, mission_id: UUID) -> bool:
        """Check if mission is currently in paused state."""
        with self._lock:
            return mission_id in self._paused_missions

    def get_pending_steering_instructions(self, mission_id: UUID) -> list[str]:
        """View pending steering instructions without consuming them."""
        with self._lock:
            return list(self._steering_queues.get(mission_id, []))

    def consume_steering_instructions(self, mission_id: UUID) -> list[str]:
        """Retrieve and drain all steering instructions for the given mission."""
        with self._lock:
            items = self._steering_queues.pop(mission_id, [])
            return list(items)

    def record_feedback(
        self,
        mission_id: UUID,
        operator: str,
        rating: int,
        comments: str,
        corrections: Sequence[str] = (),
    ) -> OperatorFeedback:
        """Store post-mission or in-flight operator feedback."""
        fb_id = uuid4()
        fb = OperatorFeedback(
            feedback_id=fb_id,
            mission_id=mission_id,
            operator=operator,
            rating=rating,
            comments=comments,
            corrections=tuple(corrections),
        )
        with self._lock:
            if mission_id not in self._feedback:
                self._feedback[mission_id] = []
            self._feedback[mission_id].append(fb)
        return fb

    def list_clarifications(
        self,
        mission_id: UUID | None = None,
        status: ClarificationStatus | None = None,
    ) -> list[ClarificationRequest]:
        """Query clarification requests with optional filtering."""
        with self._lock:
            reqs = list(self._clarifications.values())
        if mission_id is not None:
            reqs = [r for r in reqs if r.mission_id == mission_id]
        if status is not None:
            reqs = [r for r in reqs if r.status == status]
        return sorted(reqs, key=lambda r: r.created_at)

    def get_clarification(self, request_id: UUID) -> ClarificationRequest | None:
        """Retrieve a clarification request by ID."""
        with self._lock:
            return self._clarifications.get(request_id)

    def get_mission_interventions(self, mission_id: UUID) -> list[HumanIntervention]:
        """Retrieve all operator interventions recorded for a mission."""
        with self._lock:
            return list(self._interventions.get(mission_id, []))

    def get_mission_feedback(self, mission_id: UUID) -> list[OperatorFeedback]:
        """Retrieve all operator feedback entries for a mission."""
        with self._lock:
            return list(self._feedback.get(mission_id, []))

    def _enqueue_steering(self, mission_id: UUID, instruction: str) -> None:
        """Internal helper to enqueue a steering instruction under lock."""
        if mission_id not in self._steering_queues:
            self._steering_queues[mission_id] = []
        self._steering_queues[mission_id].append(instruction)
