import csv
import json
import tempfile
import unittest
from pathlib import Path

import aiosqlite

from src.crawler import AsyncCrawler
from src.storage import CSVStorage, DataStorage, JSONStorage, SQLiteStorage


class TestDay6(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.data = {
            "url": "https://example.com", "title": "Example", "text": "hello",
            "links": ["https://example.com/x"], "metadata": {"description": "a,b"},
            "crawled_at": "2026-01-01T00:00:00Z", "status_code": 200,
            "content_type": "text/html",
        }

    async def asyncTearDown(self):
        self.folder.cleanup()

    async def test_json(self):
        path = str(Path(self.folder.name) / "data.jsonl")
        storage = JSONStorage(path)
        await storage.save(self.data)
        await storage.close()
        record = json.loads(Path(path).read_text())
        self.assertEqual(record, self.data)

    async def test_csv(self):
        path = str(Path(self.folder.name) / "data.csv")
        storage = CSVStorage(path)
        await storage.save(self.data)
        await storage.close()
        with open(path, newline="", encoding="utf-8") as file:
            record = next(csv.DictReader(file))
        self.assertEqual(record["title"], "Example")
        self.assertEqual(json.loads(record["metadata"]), self.data["metadata"])

    async def test_sqlite(self):
        path = str(Path(self.folder.name) / "data.db")
        storage = SQLiteStorage(path, batch_size=5)
        await storage.save(self.data)
        await storage.close()
        async with aiosqlite.connect(path) as db:
            async with db.execute("SELECT title FROM pages") as cursor:
                self.assertEqual((await cursor.fetchone())[0], "Example")

    async def test_storage_error_does_not_stop(self):
        class BrokenStorage(DataStorage):
            async def save(self, data):
                raise OSError("failed")
            async def close(self):
                pass

        crawler = AsyncCrawler(storage=BrokenStorage())
        async def mock_fetch(url):
            return "<html><title>OK</title></html>"
        crawler.fetch_url = mock_fetch
        try:
            page = await crawler.fetch_and_parse("https://example.com")
            self.assertEqual(page["title"], "OK")
        finally:
            await crawler.close()
