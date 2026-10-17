import asyncio
import logging
from collections import Counter

from src.errors import NetworkError, TransientError


logger = logging.getLogger(__name__)


class RetryStrategy:
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retry_on: list | None = None,
        base_delay: float = 0.25,
    ):
        if max_retries < 0 or backoff_factor < 1 or base_delay < 0:
            raise ValueError("Invalid retry configuration")
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_on = tuple(retry_on if retry_on is not None else [TransientError, NetworkError])
        self.base_delay = base_delay
        self.errors_by_type = Counter()
        self.successful_retries = 0
        self.delays = []

    async def execute_with_retry(self, coro, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                result = await coro(*args, **kwargs)
                if attempt:
                    self.successful_retries += 1
                return result
            except Exception as error:
                self.errors_by_type[type(error).__name__] += 1
                retryable = isinstance(error, self.retry_on)
                if not retryable or attempt == self.max_retries:
                    logger.error("Request failed: attempt=%s type=%s", attempt + 1, type(error).__name__)
                    raise
                multiplier = 1.5 if isinstance(error, NetworkError) else 1.0
                delay = self.base_delay * self.backoff_factor ** attempt * multiplier
                self.delays.append(delay)
                logger.warning(
                    "Retry: attempt=%s error=%s delay=%.2fs",
                    attempt + 1, type(error).__name__, delay,
                )
                await asyncio.sleep(delay)

    def get_stats(self) -> dict:
        return {
            "errors_by_type": dict(self.errors_by_type),
            "successful_retries": self.successful_retries,
            "average_retry_delay": sum(self.delays) / len(self.delays) if self.delays else 0.0,
        }
