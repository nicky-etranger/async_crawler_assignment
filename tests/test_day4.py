import asyncio
import time
import unittest
from aiohttp import web

from src.crawler import AsyncCrawler
from src.rate_limiter import RateLimiter


class TestDay4(unittest.IsolatedAsyncioTestCase):
    async def test_per_domain(self):
        limiter = RateLimiter(20)
        start = time.monotonic()
        await limiter.acquire("a")
        await limiter.acquire("a")
        self.assertGreaterEqual(time.monotonic() - start, 0.045)
        start = time.monotonic()
        await limiter.acquire("b")
        self.assertLess(time.monotonic() - start, 0.045)

    async def test_global(self):
        limiter = RateLimiter(20, per_domain=False)
        start = time.monotonic()
        await limiter.acquire("a")
        await limiter.acquire("b")
        self.assertGreaterEqual(time.monotonic() - start, 0.045)

    async def test_robots(self):
        async def robots(request):
            return web.Response(text="User-agent: *\nDisallow: /blocked\nCrawl-delay: 1\n")
        async def page(request):
            return web.Response(text="ok")
        app = web.Application()
        app.router.add_get("/robots.txt", robots)
        app.router.add_get("/{tail:.*}", page)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        crawler = AsyncCrawler(respect_robots=True, requests_per_second=1000)
        try:
            self.assertEqual(await crawler.fetch_url(base + "/blocked"), "")
            self.assertEqual(await crawler.fetch_url(base + "/open"), "ok")
            self.assertEqual(len(crawler.robots_blocked), 1)
            self.assertEqual(crawler.robots.get_crawl_delay("*", base), 1)
        finally:
            await crawler.close()
            await runner.cleanup()
