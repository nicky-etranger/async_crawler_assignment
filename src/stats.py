import html
import json
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


class CrawlerStats:
    def __init__(self, crawler):
        self.crawler = crawler

    def snapshot(self) -> dict:
        crawler = self.crawler
        duration = max(time.monotonic() - crawler._crawl_started, 0.0) if crawler._crawl_started else 0.0
        total = len(crawler.visited_urls)
        speed = total / duration if duration else 0.0
        status_codes = Counter({str(code): count for code, count in crawler._status_counts.items()})
        domains = Counter(urlsplit(url).netloc for url in crawler.processed_urls)
        queued = crawler.queue.get_stats()["queued"]
        remaining = max(crawler.page_limit - total, 0)
        return {
            "total_pages": total,
            "successful": len(crawler.processed_urls),
            "failed": len(crawler.failed_urls),
            "pages_per_second": round(speed, 3),
            "status_codes": dict(status_codes),
            "top_domains": dict(domains.most_common(10)),
            "duration_seconds": round(duration, 3),
            "queued": queued,
            "active_tasks": crawler.semaphores.active_tasks,
            "progress_percent": round(100 * total / crawler.page_limit, 2) if crawler.page_limit else 100,
            "estimated_remaining_seconds": round(remaining / speed, 2) if speed and queued else None,
            "robots_blocked": len(crawler.robots_blocked),
            "rate_limit": crawler.rate_limiter.get_stats() if crawler.rate_limiter else None,
            "retries": crawler.retry_strategy.get_stats(),
            "permanent_errors": {
                url: reason for url, reason in crawler.failed_urls.items()
                if "HTTP 4" in reason and "HTTP 429" not in reason
            },
        }

    def export_to_json(self, filename: str) -> None:
        Path(filename).write_text(
            json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def export_to_html_report(self, filename: str) -> None:
        stats = self.snapshot()
        rows = "".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
            for key, value in stats.items() if not isinstance(value, dict)
        )
        bars = "".join(
            f"<div>{html.escape(key)}: {count}</div>"
            f"<div class='bar' style='width:{100 * count / max(stats['top_domains'].values(), default=1):.1f}%'></div>"
            for key, count in stats["top_domains"].items()
        )
        codes = "".join(
            f"<tr><td>{html.escape(code)}</td><td>{count}</td></tr>"
            for code, count in stats["status_codes"].items()
        )
        page = (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Crawler report</title><style>"
            "body{font:16px Arial;max-width:900px;margin:40px auto}"
            "table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ddd;text-align:left}"
            ".bar{height:14px;background:#2457a7;margin:5px 0 15px}"
            "</style><h1>Crawler report</h1>"
            f"<table>{rows}</table><h2>Status codes</h2><table>{codes}</table>"
            f"<h2>Top domains</h2>{bars}</html>"
        )
        Path(filename).write_text(page, encoding="utf-8")
