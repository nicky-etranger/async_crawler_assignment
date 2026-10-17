import argparse
import asyncio

from src.advanced import AdvancedCrawler, configure_logging
from src.storage import CSVStorage, JSONStorage, SQLiteStorage


def get_storage(filename: str):
    if filename.endswith(".csv"):
        return CSVStorage(filename)
    if filename.endswith((".sqlite", ".db")):
        return SQLiteStorage(filename)
    if filename.endswith((".json", ".jsonl")):
        return JSONStorage(filename)
    raise ValueError("Output must be .jsonl, .json, .csv, .sqlite or .db")


async def main():
    parser = argparse.ArgumentParser(description="Asynchronous web crawler")
    parser.add_argument("--urls", nargs="+")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--output")
    parser.add_argument("--config")
    parser.add_argument("--respect-robots", action="store_true", default=None)
    parser.add_argument("--rate-limit", type=float)
    args = parser.parse_args()

    if args.config:
        crawler = AdvancedCrawler.from_config(args.config)
        options = {
            "start_urls": args.urls,
            "max_pages": args.max_pages,
            "max_depth": args.max_depth,
            "respect_robots": args.respect_robots,
            "requests_per_second": args.rate_limit,
        }
        for key, value in options.items():
            if value is not None and key != "requests_per_second":
                setattr(crawler, "page_limit" if key == "max_pages" else key, value)
        if args.rate_limit is not None:
            from src.rate_limiter import RateLimiter
            crawler.rate_limiter = RateLimiter(args.rate_limit)
            crawler.robots.rate_limiter = crawler.rate_limiter
            crawler.sitemaps.rate_limiter = crawler.rate_limiter
        if args.output:
            crawler.storage = get_storage(args.output)
    else:
        if not args.urls:
            parser.error("--urls is required without --config")
        crawler = AdvancedCrawler(
            start_urls=args.urls,
            max_pages=args.max_pages if args.max_pages is not None else 100,
            max_depth=args.max_depth if args.max_depth is not None else 2,
            respect_robots=bool(args.respect_robots),
            requests_per_second=args.rate_limit,
            storage=get_storage(args.output) if args.output else None,
        )

    configure_logging()
    try:
        await crawler.crawl()
        print(crawler.get_stats())
        crawler.export_to_json("stats.json")
        crawler.export_to_html_report("report.html")
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
