"""ORION Controlled Cognitive SWE Module.

Provides:
- Model-assisted failure analysis (ANALYZE_FAILURE)
- Model-assisted fix formulation (FORMULATE_FIX)
- Bounded cognitive code modification & patch synthesis
- Deterministic syntax validation and diff inspection
- Optimistic hash-locking and workspace containment
- ApprovalService gating for patch proposals
- Preservation of ORION verification and approval authority
"""

from orion.core.swe.cognitive.contracts import (
    FailureAnalysisProposal,
    FixProposal,
)
from orion.core.swe.cognitive.errors import (
    CognitiveError,
    CognitiveModelUnavailableError,
    InvalidPatchError,
    InvalidProposalError,
    PatchApprovalRequiredError,
    PatchSyntaxError,
    PatchSynthesisError,
    PatchTooLargeError,
    StalePatchError,
    UnsafePatchPathError,
    UnsafeProposalPathError,
    UnsupportedPatchOperationError,
)
from orion.core.swe.cognitive.patch_approval import (
    PatchApprovalPackage,
    refresh_patch_approval,
    request_patch_approval,
)
from orion.core.swe.cognitive.patch_config import PatchConfig
from orion.core.swe.cognitive.patch_contracts import (
    PatchOperation,
    PatchOperationType,
    PatchProposal,
    SyntaxValidationResult,
)
from orion.core.swe.cognitive.patch_diff import PatchDiffGenerator
from orion.core.swe.cognitive.patch_syntax import PatchSyntaxValidator
from orion.core.swe.cognitive.patch_synthesizer import PatchSynthesizer
from orion.core.swe.cognitive.patch_validator import PatchValidator
from orion.core.swe.cognitive.service import SWECognitiveService
from orion.core.swe.cognitive.validator import ProposalValidator

__all__ = [
    "CognitiveError",
    "CognitiveModelUnavailableError",
    "FailureAnalysisProposal",
    "FixProposal",
    "InvalidPatchError",
    "InvalidProposalError",
    "PatchApprovalPackage",
    "PatchApprovalRequiredError",
    "PatchConfig",
    "PatchDiffGenerator",
    "PatchOperation",
    "PatchOperationType",
    "PatchProposal",
    "PatchSynthesisError",
    "PatchSynthesizer",
    "PatchSyntaxError",
    "PatchSyntaxValidator",
    "PatchTooLargeError",
    "PatchValidator",
    "ProposalValidator",
    "SWECognitiveService",
    "StalePatchError",
    "SyntaxValidationResult",
    "UnsafePatchPathError",
    "UnsafeProposalPathError",
    "UnsupportedPatchOperationError",
    "refresh_patch_approval",
    "request_patch_approval",
]
