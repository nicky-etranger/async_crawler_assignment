import asyncio
import random
import time


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float = 1.0,
        per_domain: bool = True,
        min_delay: float = 0.0,
        jitter: float = 0.0,
    ):
        if requests_per_second <= 0 or min_delay < 0 or jitter < 0:
            raise ValueError("Rate limit and delays must be valid")
        self.interval = max(1.0 / requests_per_second, min_delay)
        self.per_domain = per_domain
        self.jitter = jitter
        self._locks = {}
        self._last = {}
        self._intervals = []
        self.requests = 0
        self.started = time.monotonic()

    async def acquire(self, domain: str = None, delay: float = 0.0) -> None:
        key = domain if self.per_domain else "__global__"
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            previous = self._last.get(key)
            if previous is not None:
                remaining = max(self.interval, delay) + random.uniform(0, self.jitter) - (now - previous)
                if remaining > 0:
                    await asyncio.sleep(remaining)
                now = time.monotonic()
                self._intervals.append(now - previous)
            self._last[key] = now
            self.requests += 1

    def get_stats(self) -> dict:
        elapsed = max(time.monotonic() - self.started, 0.001)
        return {
            "requests": self.requests,
            "requests_per_second": self.requests / elapsed,
            "average_delay": sum(self._intervals) / len(self._intervals) if self._intervals else 0.0,
        }
