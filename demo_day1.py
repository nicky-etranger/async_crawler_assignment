import asyncio
import logging
import time

from src.crawler import AsyncCrawler


URLS = [
    "https://example.com",
    "https://httpbin.org/delay/1?index=1",
    "https://httpbin.org/delay/1?index=2",
    "https://httpbin.org/delay/1?index=3",
    "https://httpbin.org/delay/1?index=4",
]


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    crawler = AsyncCrawler(max_concurrent=5)
    try:
        start = time.perf_counter()
        sequential = {url: await crawler.fetch_url(url) for url in URLS}
        sequential_time = time.perf_counter() - start
        start = time.perf_counter()
        parallel = await crawler.fetch_urls(URLS)
        parallel_time = time.perf_counter() - start
    finally:
        await crawler.close()
    for url, html in parallel.items():
        print(f"{'success' if html else 'failed'}: {url}")
    print(f"Sequential: {sequential_time:.2f}s ({sum(bool(x) for x in sequential.values())} pages)")
    print(f"Parallel: {parallel_time:.2f}s ({sum(bool(x) for x in parallel.values())} pages)")


if __name__ == "__main__":
    asyncio.run(main())
