"""ORION V3 — Deep Repository Intelligence Package."""

from orion.core.repo_intel.detector import ArchitectureDetector
from orion.core.repo_intel.graph import RepoCodeGraph
from orion.core.repo_intel.impact import ChangeImpactAnalyzer
from orion.core.repo_intel.indexer import ASTSymbolIndexer
from orion.core.repo_intel.models import (
    ArchitectureProfile,
    CodeSymbol,
    ImpactReport,
    ModuleNode,
    OptimizedContext,
    SymbolType,
)
from orion.core.repo_intel.optimizer import ContextOptimizer

__all__ = [
    "ASTSymbolIndexer",
    "ArchitectureDetector",
    "ArchitectureProfile",
    "ChangeImpactAnalyzer",
    "CodeSymbol",
    "ContextOptimizer",
    "ImpactReport",
    "ModuleNode",
    "OptimizedContext",
    "RepoCodeGraph",
    "SymbolType",
]
