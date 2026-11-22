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


SHARED_PROXY_ADDRESSES = frozenset({"127.0.0.1", "::1"})


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
    def _keys(username: str, client_ip: str) -> tuple[str, ...]:
        normalized = username.strip().lower()
        account_key = f"account:{client_ip}:{normalized}"
        # Über den lokalen Port-80-Proxy erscheinen alle Geräte als
        # Loopback. Eine IP-weite Sperre würde dort alle Nutzer zugleich
        # aussperren; es greift daher nur die Sperre je Benutzerkonto.
        if client_ip in SHARED_PROXY_ADDRESSES:
            return (account_key,)
        return (account_key, f"ip:{client_ip}")

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
        keys = self._keys(username, client_ip)
        limits = (self.account_limit, self.ip_limit)
        with self._lock:
            for key, limit in zip(keys, limits):
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
                self._states[key].locked_until for key in keys
            )
            for key, state in tuple(self._states.items()):
                self._prune(state, now)
                if not state.attempts and state.locked_until <= now:
                    self._states.pop(key, None)
            return max(0, int(locked_until - now + 0.999))

    def record_success(self, username: str, client_ip: str) -> None:
        account_key = self._keys(username, client_ip)[0]
        with self._lock:
            self._states.pop(account_key, None)
