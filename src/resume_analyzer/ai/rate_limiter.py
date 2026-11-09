"""Thread-safe rate limiter for external AI API calls (NFR-03)."""

from __future__ import annotations

import collections
import time

from resume_analyzer.exceptions import AIRateLimitError


class AIRateLimiter:
    """Sliding-window rate limiter for LLM API invocation."""

    def __init__(self, requests_per_minute: int = 30) -> None:
        """Initialize AIRateLimiter with maximum allowed calls per minute."""
        self.rpm = requests_per_minute
        self.timestamps: collections.deque[float] = collections.deque()

    def acquire(self, blocking: bool = True, max_wait_s: float = 60.0) -> None:
        """Acquire permission to execute an API request."""
        now = time.time()
        # Evict timestamps older than 60 seconds
        while self.timestamps and now - self.timestamps[0] >= 60.0:
            self.timestamps.popleft()

        if len(self.timestamps) < self.rpm:
            self.timestamps.append(now)
            return

        wait_time = 60.0 - (now - self.timestamps[0])
        if not blocking or wait_time > max_wait_s:
            raise AIRateLimitError(
                f"Client-side rate limit reached ({self.rpm} RPM).",
                provider="rate_limiter",
                retry_after_s=round(wait_time, 1),
            )

        time.sleep(wait_time)
        self.timestamps.append(time.time())
