"""Centralized configuration limits for bounded patch synthesis and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchConfig:
    """Bounded configuration limits for model-proposed patches."""

    max_payload_size: int = 65_536  # Max JSON model response length (characters)
    max_affected_files: int = 10  # Max files affected by a single patch proposal
    max_changed_lines: int = 2_000  # Max total changed lines across proposal diffs
    max_file_size: int = 524_288  # Max bytes per file modification (512 KB)

    def __post_init__(self) -> None:
        if self.max_payload_size <= 0:
            raise ValueError("max_payload_size must be positive.")
        if self.max_affected_files <= 0:
            raise ValueError("max_affected_files must be positive.")
        if self.max_changed_lines <= 0:
            raise ValueError("max_changed_lines must be positive.")
        if self.max_file_size <= 0:
            raise ValueError("max_file_size must be positive.")
