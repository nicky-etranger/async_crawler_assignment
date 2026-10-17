import asyncio
import logging
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp


logger = logging.getLogger(__name__)


class RobotsParser:
    def __init__(self, session_factory, rate_limiter=None):
        self.session_factory = session_factory
        self.rate_limiter = rate_limiter
        self._parsers = {}
        self._locks = {}
        self._last_domain = None

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    async def fetch_robots(self, base_url: str) -> dict:
        origin = self._origin(base_url)
        self._last_domain = origin
        lock = self._locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin in self._parsers:
                return {"url": origin + "/robots.txt", "cached": True}
            parser = RobotFileParser()
            parser.set_url(origin + "/robots.txt")
            status = None
            try:
                if self.rate_limiter is not None:
                    await self.rate_limiter.acquire(urlsplit(base_url).netloc)
                async with self.session_factory().get(parser.url) as response:
                    status = response.status
                    if status in (401, 403):
                        parser.disallow_all = True
                    elif status == 404:
                        parser.allow_all = True
                    elif status >= 500:
                        parser.disallow_all = True
                    else:
                        response.raise_for_status()
                        parser.parse((await response.text()).splitlines())
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                logger.warning("Unable to get robots.txt for %s: %s", origin, error)
                parser.disallow_all = True
            self._parsers[origin] = parser
            return {"url": parser.url, "status": status, "cached": False}

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        parser = self._parsers.get(self._origin(url))
        return parser.can_fetch(user_agent, url) if parser is not None else True

    def get_crawl_delay(self, user_agent: str = "*", base_url: str = None) -> float:
        origin = self._origin(base_url) if base_url else self._last_domain
        parser = self._parsers.get(origin)
        return float(parser.crawl_delay(user_agent) or 0) if parser is not None else 0.0
