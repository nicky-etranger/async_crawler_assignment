import asyncio
import time
import unittest

import aiohttp
from aiohttp import web

from src.crawler import AsyncCrawler


class TestDay1(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app = web.Application()
        async def ok(request):
            return web.Response(text="ok")

        async def missing(request):
            return web.Response(status=404)

        app.router.add_get("/ok", ok)
        app.router.add_get("/missing", missing)

        async def slow(request):
            await asyncio.sleep(0.12)
            return web.Response(text="slow")

        app.router.add_get("/slow", slow)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        self.base = f"http://127.0.0.1:{self.site._server.sockets[0].getsockname()[1]}"
        self.crawler = AsyncCrawler(max_concurrent=4)

    async def asyncTearDown(self):
        await self.crawler.close()
        await self.runner.cleanup()

    async def test_valid_url(self):
        self.assertEqual(await self.crawler.fetch_url(f"{self.base}/ok"), "ok")

    async def test_http_error(self):
        self.assertEqual(await self.crawler.fetch_url(f"{self.base}/missing"), "")

    async def test_timeout(self):
        self.crawler._timeout = aiohttp.ClientTimeout(total=0.02)
        self.assertEqual(await self.crawler.fetch_url(f"{self.base}/slow"), "")

    async def test_concurrency(self):
        urls = [f"{self.base}/slow?index={index}" for index in range(4)]
        started = time.perf_counter()
        for url in urls:
            await self.crawler.fetch_url(url)
        sequential = time.perf_counter() - started
        started = time.perf_counter()
        pages = await self.crawler.fetch_urls(urls)
        parallel = time.perf_counter() - started
        self.assertTrue(all(pages.values()))
        self.assertLess(parallel, sequential)
