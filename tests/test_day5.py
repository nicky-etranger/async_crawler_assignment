import unittest
from aiohttp import web

from src.crawler import AsyncCrawler
from src.errors import PermanentError, TransientError
from src.retry import RetryStrategy


class TestDay5(unittest.IsolatedAsyncioTestCase):
    async def test_retry_and_backoff(self):
        retry = RetryStrategy(max_retries=2, base_delay=0)
        attempts = 0
        async def task():
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise TransientError("temporary")
            return "ok"
        self.assertEqual(await retry.execute_with_retry(task), "ok")
        self.assertEqual(attempts, 3)
        self.assertEqual(retry.successful_retries, 1)
        self.assertEqual(retry.delays, [0.0, 0.0])

    async def test_no_retry_on_permanent_error(self):
        retry = RetryStrategy(max_retries=2, base_delay=0)
        attempts = 0
        async def task():
            nonlocal attempts
            attempts += 1
            raise PermanentError("not found")
        with self.assertRaises(PermanentError):
            await retry.execute_with_retry(task)
        self.assertEqual(attempts, 1)

    async def test_http_503_retry_404_no_retry(self):
        calls = {"unstable": 0, "missing": 0}
        async def unstable(request):
            calls["unstable"] += 1
            return web.Response(status=503 if calls["unstable"] == 1 else 200, text="ok")
        async def missing(request):
            calls["missing"] += 1
            return web.Response(status=404)
        app = web.Application()
        app.router.add_get("/unstable", unstable)
        app.router.add_get("/missing", missing)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        crawler = AsyncCrawler(max_retries=2)
        crawler.retry_strategy.base_delay = 0
        try:
            self.assertEqual(await crawler.fetch_url(base + "/unstable"), "ok")
            self.assertEqual(await crawler.fetch_url(base + "/missing"), "")
            self.assertEqual(calls, {"unstable": 2, "missing": 1})
            self.assertEqual(dict(crawler._status_counts), {503: 1, 200: 1, 404: 1})
        finally:
            await crawler.close()
            await runner.cleanup()
