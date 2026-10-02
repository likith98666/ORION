#!/usr/bin/env python3
"""ORION Pre-Flight Environment Validation Script.

Verifies host operating environment, Python runtime, workspace permissions,
subprocess controls, and package integrity prior to production deployment.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def check_python_version() -> tuple[bool, str]:
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    if sys.version_info >= (3, 12):
        return True, f"Python {version_str} (>= 3.12 requirement satisfied)"
    return False, f"Python {version_str} is below required 3.12"


def check_git_installed() -> tuple[bool, str]:
    git_path = shutil.which("git")
    if not git_path:
        return False, "git binary not found in PATH"
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        return True, f"{res.stdout.strip()} ({git_path})"
    except Exception as exc:
        return False, f"Failed executing git: {exc}"


def check_workspace_permissions(target_dir: Path | None = None) -> tuple[bool, str]:
    test_dir = target_dir or Path(".orion_env_test")
    try:
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "probe.tmp"
        test_file.write_text("ORION_OK", encoding="utf-8")
        read_back = test_file.read_text(encoding="utf-8")
        test_file.unlink()
        test_dir.rmdir()
        if read_back == "ORION_OK":
            return True, "Workspace read/write/delete permissions verified"
        return False, "Workspace probe read back unexpected content"
    except Exception as exc:
        return False, f"Workspace filesystem check failed: {exc}"


def check_subprocess_controls() -> tuple[bool, str]:
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import sys; sys.stdout.write('OK')"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout == "OK":
            return True, "Secure subprocess invocation verified (shell=False)"
        return False, f"Subprocess returned code {res.returncode}"
    except Exception as exc:
        return False, f"Subprocess execution error: {exc}"


def check_static_assets() -> tuple[bool, str]:
    here = Path(__file__).resolve().parent.parent
    static_dir = here / "src" / "orion" / "ui" / "static"
    required_files = ["index.html", "app.css", "app.js"]
    missing = []
    for fname in required_files:
        p = static_dir / fname
        if not p.is_file() or p.stat().st_size == 0:
            missing.append(fname)
    if missing:
        return False, f"Missing or empty UI assets: {', '.join(missing)}"
    return True, f"All {len(required_files)} UI static assets verified ({static_dir})"


def run_all_checks() -> int:
    print("=" * 68)
    print("  ORION Production Pre-Flight Environment Validator")
    print("=" * 68)

    checks = [
        ("Python Version", check_python_version),
        ("Git Availability", check_git_installed),
        ("Workspace I/O", check_workspace_permissions),
        ("Subprocess Security", check_subprocess_controls),
        ("UI Static Assets", check_static_assets),
    ]

    all_passed = True
    for name, check_fn in checks:
        passed, msg = check_fn()
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name:<22}: {msg}")
        if not passed:
            all_passed = False

    print("=" * 68)
    if all_passed:
        print("  All environment pre-flight checks PASSED. System ready.")
        print("=" * 68)
        return 0
    else:
        print("  One or more pre-flight checks FAILED.")
        print("=" * 68)
        return 1


if __name__ == "__main__":
    sys.exit(run_all_checks())
