import asyncio
import time
import tracemalloc
import urllib.request

from aiohttp import web

from src.crawler import AsyncCrawler


async def main():
    async def page(request):
        return web.Response(text="<html><title>Benchmark</title></html>")

    app = web.Application()
    app.router.add_get("/{number}", page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"

    try:
        for count in (100, 500, 1000):
            urls = [f"{base}/{number}" for number in range(count)]
            crawler = AsyncCrawler(max_concurrent=50, per_domain=50, max_depth=0, max_retries=0)
            tracemalloc.start()
            started = time.perf_counter()
            try:
                pages = await crawler.crawl(urls, max_pages=count)
            finally:
                await crawler.close()
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            print(f"Async: {count} pages, success={len(pages)}, time={elapsed:.2f}s, peak={peak / 1024**2:.2f} MiB")

        urls = [f"{base}/{number}" for number in range(20)]

        def synchronous():
            for url in urls:
                with urllib.request.urlopen(url, timeout=5) as response:
                    response.read()

        start = time.perf_counter()
        await asyncio.to_thread(synchronous)
        synchronous_time = time.perf_counter() - start
        crawler = AsyncCrawler(max_concurrent=20, per_domain=20, max_retries=0)
        try:
            start = time.perf_counter()
            await crawler.fetch_urls(urls)
            asynchronous_time = time.perf_counter() - start
        finally:
            await crawler.close()
        print(f"20 pages: synchronous={synchronous_time:.2f}s async={asynchronous_time:.2f}s")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
