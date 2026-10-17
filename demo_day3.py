import asyncio
import json

import aiofiles
import logging

from src.crawler import AsyncCrawler


async def main():
    logging.basicConfig(level=logging.INFO)
    crawler = AsyncCrawler(max_concurrent=5, max_depth=2)
    try:
        results = await crawler.crawl(["https://example.com"], max_pages=20)
        async with aiofiles.open("day3_results.json", "w", encoding="utf-8") as file:
            await file.write(json.dumps(results, ensure_ascii=False, indent=2))
        print(crawler.queue.get_stats())
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
