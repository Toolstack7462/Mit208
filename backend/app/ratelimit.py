"""Minimal in-process rate limiter for failed login attempts.

Scope and honest limitations
----------------------------
State lives in this process's memory. That is sufficient for the single-worker
localhost demo this project targets, and it is what makes an online password
guessing attack against the demo accounts impractical. It is NOT sufficient for
a multi-worker or multi-instance deployment, where the counters would be
per-worker; that would need a shared store such as Redis. This limitation is
recorded in the README.

Only FAILED attempts are counted, so a user typing one wrong password then the
correct one is never locked out.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._failures[key] if now - t < self.window_seconds]
        self._failures[key] = recent
        return recent

    def is_blocked(self, key: str) -> bool:
        """True if this key has already used up its failed-attempt budget."""
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_attempts

    def retry_after(self, key: str) -> int:
        """Whole seconds until the oldest recorded failure leaves the window."""
        with self._lock:
            now = time.monotonic()
            recent = self._prune(key, now)
            if not recent:
                return 0
            return max(1, int(self.window_seconds - (now - min(recent))) + 1)

    def register_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._failures[key].append(now)

    def reset(self, key: str) -> None:
        """Clear the counter for a key — called after a successful login."""
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        """Drop all state. Used by tests to keep cases independent."""
        with self._lock:
            self._failures.clear()
