"""Repository architecture, framework, and configuration pattern detection in V3."""

from __future__ import annotations

from pathlib import Path

from orion.core.repo_intel.models import ArchitectureProfile


class ArchitectureDetector:
    """Detects repository project type, build configs, and test frameworks."""

    KNOWN_CONFIG_FILES: tuple[str, ...] = (
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "tox.ini",
        ".flake8",
        "pytest.ini",
    )

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()

    def detect_profile(self, total_files: int = 0, total_symbols: int = 0) -> ArchitectureProfile:
        """Inspect repository root and return an ArchitectureProfile."""
        configs_found: list[str] = []
        for cfg in self.KNOWN_CONFIG_FILES:
            if (self.root_dir / cfg).exists():
                configs_found.append(cfg)

        # Detect source roots
        source_roots: list[str] = []
        for candidate in ("src", "lib", "app"):
            cand_path = self.root_dir / candidate
            if cand_path.exists() and cand_path.is_dir():
                source_roots.append(candidate)
        if not source_roots:
            source_roots.append(".")

        # Detect test runner
        test_runner = "unittest"
        if (self.root_dir / "pytest.ini").exists():
            test_runner = "pytest"
        elif (self.root_dir / "pyproject.toml").exists():
            try:
                pyproj = (self.root_dir / "pyproject.toml").read_text(encoding="utf-8")
                if "pytest" in pyproj:
                    test_runner = "pytest"
            except Exception:
                pass

        # Framework detection
        framework = "python-standard"
        if (self.root_dir / "pyproject.toml").exists():
            framework = "python-pyproject"
        elif (self.root_dir / "setup.py").exists():
            framework = "python-setuptools"

        return ArchitectureProfile(
            framework=framework,
            test_runner=test_runner,
            config_files=tuple(configs_found),
            source_roots=tuple(source_roots),
            total_files=total_files,
            total_symbols=total_symbols,
        )
