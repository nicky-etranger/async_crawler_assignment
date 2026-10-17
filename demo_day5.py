import asyncio
import json
from aiohttp import web

from src.crawler import AsyncCrawler


async def main():
    attempts = {"count": 0}

    async def unstable(request):
        attempts["count"] += 1
        return web.Response(status=503 if attempts["count"] < 3 else 200, text="ok")

    async def missing(request):
        return web.Response(status=404)

    app = web.Application()
    app.router.add_get("/unstable", unstable)
    app.router.add_get("/missing", missing)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8081)
    await site.start()
    crawler = AsyncCrawler(max_retries=3)
    try:
        results = await crawler.fetch_urls([
            "http://127.0.0.1:8081/unstable",
            "http://127.0.0.1:8081/missing",
        ])
        print(json.dumps({"results": results, "errors": crawler._errors,
                          "retry_stats": crawler.retry_strategy.get_stats()}, indent=2))
    finally:
        await crawler.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
