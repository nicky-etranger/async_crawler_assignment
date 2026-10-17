import asyncio
import logging
from collections import Counter
import time
from urllib.parse import urlsplit

import aiohttp

from src.parser import HTMLParser
from src.queue import CrawlerQueue
from src.semaphores import SemaphoreManager
from src.rate_limiter import RateLimiter
from src.robots import RobotsParser
from src.errors import NetworkError, PermanentError, TransientError
from src.retry import RetryStrategy


logger = logging.getLogger(__name__)


class AsyncCrawler:
    def __init__(
        self,
        max_concurrent: int = 10,
        max_depth: int = 2,
        per_domain: int = 2,
        requests_per_second: float | None = None,
        respect_robots: bool = False,
        min_delay: float = 0.0,
        jitter: float = 0.0,
        user_agent: str = "AsyncCrawler/1.0",
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be positive")
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if requests_per_second is not None and requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.max_concurrent = max_concurrent
        self.max_depth = max_depth
        self.semaphores = SemaphoreManager(max_concurrent, per_domain)
        self.visited_urls = set()
        self.failed_urls = {}
        self.processed_urls = {}
        self.queue = CrawlerQueue()
        self._crawl_started = 0.0
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.rate_limiter = (
            RateLimiter(requests_per_second if requests_per_second is not None else (1.0 if respect_robots else 1_000_000), min_delay=min_delay, jitter=jitter)
            if requests_per_second is not None or min_delay > 0 or jitter > 0 or respect_robots
            else None
        )
        self.robots = RobotsParser(self._get_session, self.rate_limiter)
        self.robots_blocked = set()
        self._errors = {}
        self._responses = {}
        self._status_counts = Counter()
        self.retry_strategy = RetryStrategy(max_retries=max_retries, backoff_factor=backoff_factor)
        self._timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
        self._session: aiohttp.ClientSession | None = None
        self.parser = HTMLParser()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=self.max_concurrent)
            self._session = aiohttp.ClientSession(
                timeout=self._timeout, connector=connector
            )
        return self._session

    async def _fetch_once(self, url: str, attempt: int) -> tuple[str, int, str]:
        multiplier = 1.5 ** (attempt - 1)
        timeout = aiohttp.ClientTimeout(
            total=self._timeout.total * multiplier if self._timeout.total else None,
            connect=self._timeout.connect * multiplier if self._timeout.connect else None,
            sock_read=self._timeout.sock_read * multiplier if self._timeout.sock_read else None,
        )
        try:
            async with self.semaphores.slot(urlsplit(url).netloc):
                if self.rate_limiter is not None:
                    delay = self.robots.get_crawl_delay(self.user_agent, url) if self.respect_robots else 0
                    await self.rate_limiter.acquire(urlsplit(url).netloc, delay)
                async with self._get_session().get(
                    url, headers={"User-Agent": self.user_agent}, timeout=timeout
                ) as response:
                    self._status_counts[response.status] += 1
                    if response.status in (429, 500, 503) or response.status >= 500:
                        raise TransientError(f"HTTP {response.status}: {url}")
                    if response.status in (401, 403, 404) or response.status >= 400:
                        raise PermanentError(f"HTTP {response.status}: {url}")
                    return await response.text(), response.status, response.content_type
        except asyncio.TimeoutError as error:
            raise TransientError(f"Timeout: {url}") from error
        except aiohttp.ClientResponseError as error:
            error_class = TransientError if error.status == 429 or error.status >= 500 else PermanentError
            raise error_class(f"HTTP {error.status}: {url}") from error
        except aiohttp.ClientError as error:
            raise NetworkError(f"{type(error).__name__}: {url}") from error

    async def fetch_url(self, url: str) -> str:
        logger.info("Fetch started: %s", url)
        if self.respect_robots:
            await self.robots.fetch_robots(url)
            if not self.robots.can_fetch(url, self.user_agent):
                self.robots_blocked.add(url)
                self._errors[url] = "Disallowed by robots.txt"
                logger.info("Robots blocked: %s", url)
                return ""
        attempt = 0

        async def run():
            nonlocal attempt
            attempt += 1
            logger.info("Fetch attempt %s: %s", attempt, url)
            return await self._fetch_once(url, attempt)

        try:
            html, status, content_type = await self.retry_strategy.execute_with_retry(run)
            self._responses[url] = {"status_code": status, "content_type": content_type}
            self._errors.pop(url, None)
            logger.info("Fetch completed: %s", url)
            return html
        except (TransientError, PermanentError, NetworkError) as error:
            self._errors[url] = str(error)
            logger.error("Fetch failed: url=%s type=%s error=%s", url, type(error).__name__, error)
            return ""

    async def fetch_urls(self, urls: list[str]) -> dict[str, str]:
        pages = await asyncio.gather(*(self.fetch_url(url) for url in urls))
        return dict(zip(urls, pages))

    async def fetch_and_parse(self, url: str) -> dict:
        html = await self.fetch_url(url)
        if not html:
            return {"url": url, "error": self._errors.get(url, "fetch failed")}
        return await self.parser.parse_html(html, url)

    async def crawl(
        self,
        start_urls: list[str],
        max_pages: int = 100,
        same_domain_only: bool = True,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, dict]:
        if max_pages < 0:
            raise ValueError("max_pages must be non-negative")
        self.queue = CrawlerQueue()
        self.visited_urls = set()
        self.failed_urls = {}
        self.processed_urls = {}
        self._crawl_started = time.monotonic()
        self._status_counts.clear()
        self._responses.clear()
        origins = {urlsplit(url).netloc for url in start_urls}

        def allowed(url: str) -> bool:
            parts = urlsplit(url)
            return (
                parts.scheme in ("http", "https")
                and bool(parts.netloc)
                and (not same_domain_only or parts.netloc in origins)
                and (not include_patterns or any(p in url for p in include_patterns))
                and not any(p in url for p in (exclude_patterns or []))
            )

        for url in start_urls:
            if len(self.queue._seen) >= max_pages:
                break
            if allowed(url):
                self.queue.add_url(url)

        async def worker():
            while True:
                url = await self.queue.get_next()
                self.visited_urls.add(url)
                try:
                    data = await self.fetch_and_parse(url)
                    if "error" in data:
                        self.failed_urls[url] = data["error"]
                        self.queue.mark_failed(url, data["error"])
                    else:
                        self.processed_urls[url] = data
                        depth = self.queue.depth_for(url)
                        if depth < self.max_depth:
                            for link in data["links"]:
                                if len(self.queue._seen) >= max_pages:
                                    break
                                if allowed(link):
                                    self.queue.add_url(link, depth=depth + 1)
                        self.queue.mark_processed(url)
                except Exception as error:
                    self.failed_urls[url] = str(error)
                    self.queue.mark_failed(url, str(error))
                    logger.error("Crawl failed for %s: %s", url, error)
                self._log_progress()

        workers = [asyncio.create_task(worker()) for _ in range(min(max_pages, self.max_concurrent))]
        try:
            await self.queue.join()
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        return self.processed_urls

    def _log_progress(self) -> None:
        elapsed = max(time.monotonic() - self._crawl_started, 0.001)
        logger.info(
            "Processed=%s queued=%s failed=%s speed=%.2f pages/s",
            len(self.visited_urls), self.queue.get_stats()["queued"],
            len(self.failed_urls), len(self.visited_urls) / elapsed,
        )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
