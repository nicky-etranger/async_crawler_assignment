import asyncio
import json

from src.crawler import AsyncCrawler


async def main():
    crawler = AsyncCrawler()
    try:
        for url in ["https://example.com", "https://www.python.org"]:
            data = await crawler.fetch_and_parse(url)
            print(json.dumps({
                "url": url,
                "title": data.get("title", ""),
                "links": data.get("links", [])[:5],
                "links_count": len(data.get("links", [])),
                "text_length": len(data.get("text", "")),
                "images_count": len(data.get("images", [])),
            }, ensure_ascii=False, indent=2))
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
