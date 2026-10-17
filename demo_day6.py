import asyncio

import aiosqlite

from src.crawler import AsyncCrawler
from src.storage import CSVStorage, JSONStorage, SQLiteStorage


async def main():
    for storage in (
        JSONStorage("results.jsonl"),
        CSVStorage("results.csv"),
        SQLiteStorage("results.db", batch_size=5),
    ):
        crawler = AsyncCrawler(storage=storage, max_depth=0)
        try:
            data = await crawler.crawl(["https://example.com"], max_pages=1)
            print(type(storage).__name__, len(data))
        finally:
            await crawler.close()
    async with aiosqlite.connect("results.db") as db:
        async with db.execute("SELECT url, title FROM pages") as cursor:
            print(await cursor.fetchall())


if __name__ == "__main__":
    asyncio.run(main())
