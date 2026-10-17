import unittest

from src.parser import HTMLParser


class TestDay2(unittest.IsolatedAsyncioTestCase):
    async def test_html_and_relative_urls(self):
        parser = HTMLParser()
        data = await parser.parse_html(
            '<html><head><title>Example</title><meta name="description" content="test"></head>'
            '<body><main><h1>Hello</h1><a href="/news">News</a>'
            '<img src="/img.png" alt="photo"><ul><li>A</li></ul>'
            '<table><tr><th>name</th><td>A</td></tr></table></main></body></html>',
            "https://example.com/start",
        )
        self.assertEqual(data["title"], "Example")
        self.assertIn("https://example.com/news", data["links"])
        self.assertEqual(data["images"][0]["alt"], "photo")
        self.assertEqual(data["tables"][0][0], ["name", "A"])
        self.assertEqual(data["metadata"]["description"], "test")

    async def test_broken_html(self):
        parser = HTMLParser()
        data = await parser.parse_html("<title>Broken<h1>Title", "https://example.com")
        self.assertEqual(data["url"], "https://example.com")
        self.assertIn("title", data)

    async def test_url_validation(self):
        parser = HTMLParser()
        data = await parser.parse_html(
            '<a href="javascript:alert(1)">Bad</a><a href="/x#frag">Good</a>',
            "https://example.com",
        )
        self.assertEqual(data["links"], ["https://example.com/x"])
