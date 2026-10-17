import asyncio
import logging

from src.crawler import AsyncCrawler


async def main():
    logging.basicConfig(level=logging.INFO)
    crawler = AsyncCrawler(
        max_concurrent=5, max_depth=1, requests_per_second=2,
        respect_robots=True, min_delay=0.5, user_agent="MyBot/1.0",
    )
    try:
        await crawler.crawl(["https://www.python.org"], max_pages=5)
        print(crawler.rate_limiter.get_stats())
        print("robots blocked:", len(crawler.robots_blocked))
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
