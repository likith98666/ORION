"""Context optimizer providing bounded, token-efficient neighborhoods for LLM reasoning in V3."""

from __future__ import annotations

from orion.core.repo_intel.graph import RepoCodeGraph
from orion.core.repo_intel.models import OptimizedContext


class ContextOptimizer:
    """Extracts tightly bounded, highly-relevant repository neighborhoods for model prompts."""

    def __init__(self, code_graph: RepoCodeGraph) -> None:
        self.code_graph = code_graph

    def build_context(
        self,
        target_file: str,
        max_tokens: int = 4000,
    ) -> OptimizedContext:
        """Construct an optimized context neighborhood around target_file."""
        norm_target = target_file.replace("\\", "/")
        mod_node = self.code_graph.modules.get(norm_target)

        symbols = tuple(mod_node.symbols.values()) if mod_node else ()
        imports = tuple(sorted(mod_node.imports)) if mod_node else ()
        tests = tuple(self.code_graph.get_tests_for_file(norm_target))
        neighbors = tuple(sorted(self.code_graph.get_dependencies(norm_target, recursive=False)))

        # Build clean formatted context snippet
        lines: list[str] = [
            f"# Bounded Repository Context: {norm_target}",
            f"Module: {mod_node.module_name if mod_node else 'unknown'}",
            "",
            "## Defined Symbols",
        ]

        for sym in symbols:
            sig_line = sym.signature or sym.name
            lines.append(f"- Line {sym.line_number}: `{sig_line}` ({sym.symbol_type.value})")
            if sym.docstring:
                clean_doc = sym.docstring.strip().splitlines()[0]
                lines.append(f"  Doc: {clean_doc}")

        lines.extend(
            [
                "",
                "## Imported Dependencies",
            ]
        )
        for imp in imports:
            lines.append(f"- `import {imp}`")

        if tests:
            lines.extend(
                [
                    "",
                    "## Covering Tests",
                ]
            )
            for t in tests:
                lines.append(f"- `{t}`")

        # Include raw target file snippet if under token budget
        target_full_path = self.code_graph.root_dir / norm_target
        if target_full_path.exists():
            try:
                raw_code = target_full_path.read_text(encoding="utf-8")
                code_lines = raw_code.splitlines()
                preview = "\n".join(code_lines[:150])  # Bounded to first 150 lines
                lines.extend(
                    [
                        "",
                        "## Source Preview (Target File)",
                        "```python",
                        preview,
                        "```",
                    ]
                )
            except Exception:
                pass

        snippet = "\n".join(lines)
        token_estimate = max(1, len(snippet) // 4)

        return OptimizedContext(
            target_path=norm_target,
            symbols=symbols,
            relevant_imports=imports,
            relevant_tests=tests,
            neighbor_files=neighbors,
            token_estimate=token_estimate,
            context_snippet=snippet,
        )
