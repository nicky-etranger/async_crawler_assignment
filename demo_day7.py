import asyncio
from src.advanced import AdvancedCrawler, configure_logging


async def main():
    configure_logging()
    crawler = AdvancedCrawler.from_config("config.json")
    try:
        await crawler.crawl()
        print(crawler.get_stats())
        crawler.export_to_json("stats.json")
        crawler.export_to_html_report("report.html")
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
