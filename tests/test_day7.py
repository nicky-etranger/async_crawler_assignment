import json
import tempfile
import unittest
from pathlib import Path

from aiohttp import web

from src.advanced import AdvancedCrawler


class TestDay7(unittest.IsolatedAsyncioTestCase):
    async def test_sitemap_index_and_reports(self):
        async def index(request):
            return web.Response(text=(
                '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<sitemap><loc>' + base + '/site.xml</loc></sitemap></sitemapindex>'
            ), content_type="application/xml")
        async def sitemap(request):
            return web.Response(text=(
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>' + base + '/a</loc></url><url><loc>' + base + '/b</loc></url></urlset>'
            ), content_type="application/xml")
        async def page(request):
            return web.Response(text="<html><title>Test</title></html>", content_type="text/html")
        app = web.Application()
        app.router.add_get("/index.xml", index)
        app.router.add_get("/site.xml", sitemap)
        app.router.add_get("/{name}", page)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        crawler = AdvancedCrawler(sitemap_urls=[base + "/index.xml"], max_pages=2)
        try:
            pages = await crawler.crawl()
            self.assertEqual(len(pages), 2)
            self.assertEqual(crawler.get_stats()["successful"], 2)
            with tempfile.TemporaryDirectory() as folder:
                stats_file = Path(folder) / "stats.json"
                html_file = Path(folder) / "report.html"
                crawler.export_to_json(str(stats_file))
                crawler.export_to_html_report(str(html_file))
                self.assertEqual(json.loads(stats_file.read_text())["successful"], 2)
                self.assertIn("Crawler report", html_file.read_text())
        finally:
            await crawler.close()
            await runner.cleanup()

    async def test_from_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"start_urls": ["https://example.com"], "max_pages": 7}))
            crawler = AdvancedCrawler.from_config(str(path))
            try:
                self.assertEqual(crawler.page_limit, 7)
            finally:
                await crawler.close()
