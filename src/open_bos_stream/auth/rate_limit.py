"""Begrenzt fehlgeschlagene Anmeldungen ohne externe Abhaengigkeiten."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Callable


@dataclass
class _AttemptState:
    attempts: deque[float]
    locked_until: float = 0.0


class LoginRateLimiter:
    """Temporäre Sperre je Benutzer/IP sowie gegen IP-weites Durchprobieren."""

    def __init__(
        self,
        *,
        account_limit: int = 5,
        ip_limit: int = 20,
        window_seconds: int = 5 * 60,
        lock_seconds: int = 15 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.account_limit = account_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self._clock = clock
        self._states: dict[str, _AttemptState] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(username: str, client_ip: str) -> tuple[str, str]:
        normalized = username.strip().lower()
        return (
            f"account:{client_ip}:{normalized}",
            f"ip:{client_ip}",
        )

    def _prune(self, state: _AttemptState, now: float) -> None:
        threshold = now - self.window_seconds
        while state.attempts and state.attempts[0] <= threshold:
            state.attempts.popleft()

    def retry_after(self, username: str, client_ip: str) -> int:
        now = self._clock()
        with self._lock:
            retry_after = 0.0
            for key in self._keys(username, client_ip):
                state = self._states.get(key)
                if state is None:
                    continue
                self._prune(state, now)
                retry_after = max(retry_after, state.locked_until - now)
            return max(0, int(retry_after + 0.999))

    def record_failure(self, username: str, client_ip: str) -> int:
        now = self._clock()
        account_key, ip_key = self._keys(username, client_ip)
        with self._lock:
            for key, limit in (
                (account_key, self.account_limit),
                (ip_key, self.ip_limit),
            ):
                state = self._states.setdefault(
                    key,
                    _AttemptState(deque()),
                )
                self._prune(state, now)
                state.attempts.append(now)
                if len(state.attempts) >= limit:
                    state.locked_until = max(
                        state.locked_until,
                        now + self.lock_seconds,
                    )
            locked_until = max(
                self._states[account_key].locked_until,
                self._states[ip_key].locked_until,
            )
            for key, state in tuple(self._states.items()):
                self._prune(state, now)
                if not state.attempts and state.locked_until <= now:
                    self._states.pop(key, None)
            return max(0, int(locked_until - now + 0.999))

    def record_success(self, username: str, client_ip: str) -> None:
        account_key, _ = self._keys(username, client_ip)
        with self._lock:
            self._states.pop(account_key, None)
