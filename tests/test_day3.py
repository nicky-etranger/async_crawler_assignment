import unittest

from src.crawler import AsyncCrawler
from src.queue import CrawlerQueue
from src.semaphores import SemaphoreManager


class TestDay3(unittest.IsolatedAsyncioTestCase):
    async def test_priority_and_uniqueness(self):
        queue = CrawlerQueue()
        self.assertTrue(queue.add_url("https://a.test", priority=10))
        self.assertTrue(queue.add_url("https://b.test", priority=1))
        self.assertFalse(queue.add_url("https://b.test", priority=0))
        self.assertEqual(await queue.get_next(), "https://b.test")
        queue.mark_processed("https://b.test")
        self.assertEqual(await queue.get_next(), "https://a.test")
        queue.mark_failed("https://a.test", "error")
        self.assertEqual(queue.get_stats()["failed"], 1)

    async def test_depth_and_filters(self):
        crawler = AsyncCrawler(max_depth=1)
        async def fake_fetch(url):
            return {
                "url": url,
                "links": ["https://a.test/one", "https://b.test/external", "https://a.test/exclude"],
            }
        crawler.fetch_and_parse = fake_fetch
        try:
            result = await crawler.crawl(
                ["https://a.test"], max_pages=10,
                same_domain_only=True, exclude_patterns=["exclude"],
            )
            self.assertEqual(set(result), {"https://a.test", "https://a.test/one"})
            self.assertEqual(len(crawler.visited_urls), 2)
        finally:
            await crawler.close()

    async def test_concurrency_manager(self):
        manager = SemaphoreManager(2, 1)
        async with manager.slot("a.test"):
            self.assertEqual(manager.active_tasks, 1)
        self.assertEqual(manager.active_tasks, 0)
