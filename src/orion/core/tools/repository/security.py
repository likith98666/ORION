from pathlib import Path

from orion.core.tools.repository.errors import ProtectedPathError

PROTECTED_EXACT_NAMES: frozenset[str] = frozenset({
    ".env",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
})

PROTECTED_PREFIXES: tuple[str, ...] = (
    ".env.",
    "credentials.",
    "secrets.",
)

PROTECTED_EXTENSIONS: frozenset[str] = frozenset({
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".pkcs12",
    ".keystore",
    ".jks",
})


def is_protected_path(path: str | Path) -> bool:
    """Return True if path points to a known sensitive/secret credential file or .git directory."""
    path_obj = Path(path)
    name = path_obj.name.lower()

    # Disallow internal .git directories and metadata
    parts = [p.lower() for p in path_obj.parts]
    if ".git" in parts:
        return True

    if name in PROTECTED_EXACT_NAMES:
        return True

    for prefix in PROTECTED_PREFIXES:
        if name.startswith(prefix):
            return True

    if path_obj.suffix.lower() in PROTECTED_EXTENSIONS:
        return True

    return False


def assert_not_protected(path: str | Path) -> None:
    """Raise ProtectedPathError if path matches protected secret patterns."""
    if is_protected_path(path):
        raise ProtectedPathError(
            f"Access to protected secret or credential path '{path}' is forbidden."
        )
