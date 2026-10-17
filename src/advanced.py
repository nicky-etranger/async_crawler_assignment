import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.crawler import AsyncCrawler
from src.sitemap import SitemapParser
from src.stats import CrawlerStats
from src.storage import CSVStorage, JSONStorage, SQLiteStorage


class AdvancedCrawler(AsyncCrawler):
    def __init__(
        self,
        start_urls: list[str] | None = None,
        sitemap_urls: list[str] | None = None,
        max_pages: int = 100,
        same_domain_only: bool = True,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.start_urls = start_urls or []
        self.sitemap_urls = sitemap_urls or []
        self.page_limit = max_pages
        self.same_domain_only = same_domain_only
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.sitemaps = SitemapParser(self._get_session, self.rate_limiter)
        self.stats = CrawlerStats(self)

    @classmethod
    def from_config(cls, filename: str):
        config = json.loads(Path(filename).read_text(encoding="utf-8"))
        storage_config = config.pop("storage", None)
        if storage_config:
            storage_type = storage_config["type"].lower()
            filename = storage_config["filename"]
            formats = {
                "json": JSONStorage,
                "jsonl": JSONStorage,
                "csv": CSVStorage,
                "sqlite": SQLiteStorage,
            }
            if storage_type not in formats:
                raise ValueError("Unsupported storage type")
            config["storage"] = formats[storage_type](filename)
        return cls(**config)

    async def crawl(
        self,
        start_urls: list[str] | None = None,
        max_pages: int | None = None,
        same_domain_only: bool | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, dict]:
        urls = list(start_urls if start_urls is not None else self.start_urls)
        for sitemap in self.sitemap_urls:
            urls.extend(await self.sitemaps.fetch_sitemap(sitemap))
        self.page_limit = max_pages if max_pages is not None else self.page_limit
        return await super().crawl(
            list(dict.fromkeys(urls)), max_pages=self.page_limit,
            same_domain_only=self.same_domain_only if same_domain_only is None else same_domain_only,
            include_patterns=self.include_patterns if include_patterns is None else include_patterns,
            exclude_patterns=self.exclude_patterns if exclude_patterns is None else exclude_patterns,
        )

    def _log_progress(self) -> None:
        super()._log_progress()
        logging.getLogger(__name__).info("Progress: %s", self.get_stats())

    def get_stats(self) -> dict:
        return self.stats.snapshot()

    def export_to_json(self, filename: str) -> None:
        self.stats.export_to_json(filename)

    def export_to_html_report(self, filename: str) -> None:
        self.stats.export_to_html_report(filename)


def configure_logging(filename: str = "crawler.log", level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    format_string = "%(asctime)s %(levelname)s %(name)s %(message)s"
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for handler in (
        logging.StreamHandler(),
        RotatingFileHandler(filename, maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
    ):
        handler.setFormatter(logging.Formatter(format_string))
        root.addHandler(handler)
