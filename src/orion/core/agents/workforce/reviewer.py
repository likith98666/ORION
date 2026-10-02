"""Independent multi-stage reviewer evaluating security, syntax, and test coverage in V4."""

from __future__ import annotations

import ast
from uuid import UUID, uuid4

from orion.core.agents.workforce.models import AgentProposal, ReviewVerdict


class IndependentReviewer:
    """Rigorous gatekeeper conducting independent security, quality, and test reviews."""

    def __init__(self, reviewer_id: UUID | None = None) -> None:
        self.reviewer_id = reviewer_id or uuid4()

    def review(self, proposal: AgentProposal) -> ReviewVerdict:
        """Execute multi-stage review against an agent proposal."""
        comments: list[str] = []
        security_clean = True
        code_clean = True
        risk_level = "low"

        # 1. Security Review: Scan patch content for dangerous constructs
        patch_text = proposal.patch_content.lower()
        forbidden_patterns = (
            "os.system(",
            "shell=true",
            "eval(",
            "exec(",
            "__import__('os')",
            "rmdir -rf",
            "format c:",
        )
        for pat in forbidden_patterns:
            if pat in patch_text:
                security_clean = False
                risk_level = "critical"
                comments.append(f"Security Alert: Detected unsafe pattern '{pat}'.")

        # 2. Code Quality & Syntax Review: Validate AST syntax if full python file
        if proposal.patch_content.strip() and not proposal.patch_content.startswith("---"):
            try:
                ast.parse(proposal.patch_content)
            except SyntaxError as exc:
                code_clean = False
                comments.append(f"Syntax Error in proposal: {exc.msg} at line {exc.lineno}.")

        # 3. Test Impact Review: Ensure proposal addresses test coverage
        has_tests = (
            any("test" in f.lower() for f in proposal.target_files)
            or "test" in proposal.rationale.lower()
        )
        if not has_tests:
            if risk_level == "low":
                risk_level = "medium"
            comments.append("Advisory: Proposal does not explicitly include targeted tests.")

        # Verdict Resolution
        if not security_clean:
            status = "REJECTED"
        elif not code_clean:
            status = "CHANGES_REQUESTED"
        else:
            status = "APPROVED"

        return ReviewVerdict(
            verdict_id=uuid4(),
            reviewer_id=self.reviewer_id,
            status=status,
            security_clean=security_clean,
            code_quality_clean=code_clean,
            comments=tuple(comments),
            risk_level=risk_level,
        )
