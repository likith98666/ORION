from __future__ import annotations

import threading
import time
from collections import deque


class TokenBucketRateLimiter:
    """In-process, thread-safe sliding window rate limiter with bounded memory."""

    def __init__(
        self,
        default_limit_per_minute: int = 120,
        cleanup_interval_seconds: float = 300.0,
        max_tracked_keys: int = 10000,
    ) -> None:
        self._default_limit = default_limit_per_minute
        self._cleanup_interval = cleanup_interval_seconds
        self._max_tracked_keys = max_tracked_keys
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = {}
        self._last_cleanup = time.time()

    def check_rate_limit(
        self, key: str, limit_per_minute: int | None = None
    ) -> tuple[bool, float]:
        """Check whether an action by `key` is allowed under the rate limit.

        Returns:
            (allowed: bool, retry_after_seconds: float)
        """
        limit = limit_per_minute if limit_per_minute is not None else self._default_limit
        now = time.time()
        window_duration = 60.0

        with self._lock:
            self._maybe_cleanup(now)

            if key not in self._windows:
                if len(self._windows) >= self._max_tracked_keys:
                    # Prune oldest keys if max capacity reached
                    self._prune_oldest()
                self._windows[key] = deque()

            window = self._windows[key]

            # Discard timestamps older than 60 seconds
            while window and window[0] <= now - window_duration:
                window.popleft()

            if len(window) < limit:
                window.append(now)
                return True, 0.0

            # Rate limit exceeded: calculate retry-after
            oldest_ts = window[0]
            retry_after = max(0.1, round((oldest_ts + window_duration) - now, 2))
            return False, retry_after

    def reset(self) -> None:
        """Clear all rate limit windows (for testing)."""
        with self._lock:
            self._windows.clear()
            self._last_cleanup = time.time()

    def _maybe_cleanup(self, now: float) -> None:
        """Prune idle keys older than cleanup interval."""
        if now - self._last_cleanup < self._cleanup_interval:
            return

        window_duration = 60.0
        keys_to_remove = [
            k
            for k, win in self._windows.items()
            if not win or win[-1] <= now - window_duration
        ]
        for k in keys_to_remove:
            del self._windows[k]
        self._last_cleanup = now

    def _prune_oldest(self) -> None:
        """Remove up to 10% of idle keys when tracking cap is reached."""
        sorted_keys = sorted(
            self._windows.keys(),
            key=lambda k: self._windows[k][-1] if self._windows[k] else 0.0,
        )
        prune_count = max(1, len(sorted_keys) // 10)
        for k in sorted_keys[:prune_count]:
            del self._windows[k]
