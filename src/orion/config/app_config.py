from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EnvironmentType = Literal["development", "testing", "production"]


@dataclass(frozen=True)
class AppConfig:
    """Production-grade application configuration for ORION."""

    host: str = "127.0.0.1"
    port: int = 8000
    workspace: Path = Path(".").resolve()
    environment: EnvironmentType = "development"
    max_request_body_bytes: int = 10 * 1024 * 1024  # 10 MB default cap
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    mission_rate_limit_per_minute: int = 20
    redaction_enabled: bool = True
    known_secrets: tuple[str, ...] = ()
    enable_cors: bool = True
    cors_allowed_origins: tuple[str, ...] = ("*",)
    shutdown_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not self.host or not self.host.strip():
            raise ValueError("Host address cannot be empty.")

        if not 0 <= self.port <= 65535:
            raise ValueError(f"Port must be between 0 and 65535, got {self.port}")

        if self.max_request_body_bytes <= 0:
            raise ValueError("max_request_body_bytes must be greater than zero.")

        if self.rate_limit_per_minute <= 0:
            raise ValueError("rate_limit_per_minute must be greater than zero.")

        if self.mission_rate_limit_per_minute <= 0:
            raise ValueError("mission_rate_limit_per_minute must be greater than zero.")

        if self.environment not in ("development", "testing", "production"):
            raise ValueError(
                f"Invalid environment '{self.environment}'. "
                "Must be development, testing, or production."
            )

        # Production security constraints
        if self.environment == "production":
            # In production, workspace must exist and be an absolute directory
            if not self.workspace.is_absolute():
                raise ValueError("In production, workspace must be an absolute path.")
            if not self.workspace.exists():
                raise ValueError(f"In production, workspace directory must exist: {self.workspace}")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    def __repr__(self) -> str:
        # Never log or expose secrets in string representation
        masked_secrets = f"({len(self.known_secrets)} registered)" if self.known_secrets else "()"
        return (
            f"AppConfig(host={self.host!r}, port={self.port}, "
            f"workspace={self.workspace!r}, environment={self.environment!r}, "
            f"max_request_body_bytes={self.max_request_body_bytes}, "
            f"rate_limit_enabled={self.rate_limit_enabled}, "
            f"known_secrets={masked_secrets})"
        )

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        argv_workspace: Path | None = None,
        argv_host: str | None = None,
        argv_port: int | None = None,
    ) -> AppConfig:
        """Construct AppConfig from environment variables with optional CLI overrides."""
        source_env = os.environ if env is None else env

        raw_env = source_env.get("ORION_ENV", "development").lower().strip()
        environment: EnvironmentType = (
            "production"
            if raw_env in ("production", "prod")
            else ("testing" if raw_env in ("testing", "test") else "development")
        )

        host = argv_host or source_env.get("ORION_HOST", "127.0.0.1")
        port_str = str(argv_port) if argv_port is not None else source_env.get("ORION_PORT", "8000")
        try:
            port = int(port_str)
        except ValueError:
            port = 8000

        ws_str = str(argv_workspace) if argv_workspace else source_env.get("ORION_WORKSPACE", ".")
        workspace = Path(ws_str).resolve()

        max_body_str = source_env.get("ORION_MAX_REQUEST_BYTES", str(10 * 1024 * 1024))
        try:
            max_request_body_bytes = int(max_body_str)
        except ValueError:
            max_request_body_bytes = 10 * 1024 * 1024

        rate_limit_enabled = source_env.get("ORION_RATE_LIMIT_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        rate_limit_str = source_env.get("ORION_RATE_LIMIT_PER_MINUTE", "120")
        try:
            rate_limit_per_minute = int(rate_limit_str)
        except ValueError:
            rate_limit_per_minute = 120

        mission_limit_str = source_env.get("ORION_MISSION_RATE_LIMIT_PER_MINUTE", "20")
        try:
            mission_rate_limit_per_minute = int(mission_limit_str)
        except ValueError:
            mission_rate_limit_per_minute = 20

        redaction_enabled = source_env.get("ORION_REDACTION_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        # Extract known secrets from environment variables (keys, tokens, passwords)
        known_secrets_list: list[str] = []
        secret_keywords = ("API_KEY", "SECRET", "PASSWORD", "TOKEN", "AUTH")
        for k, v in source_env.items():
            if any(kw in k.upper() for kw in secret_keywords) and v and len(v) >= 4:
                known_secrets_list.append(v)

        return cls(
            host=host,
            port=port,
            workspace=workspace,
            environment=environment,
            max_request_body_bytes=max_request_body_bytes,
            rate_limit_enabled=rate_limit_enabled,
            rate_limit_per_minute=rate_limit_per_minute,
            mission_rate_limit_per_minute=mission_rate_limit_per_minute,
            redaction_enabled=redaction_enabled,
            known_secrets=tuple(known_secrets_list),
        )
