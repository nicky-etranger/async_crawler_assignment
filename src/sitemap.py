import asyncio
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit

import aiohttp


logger = logging.getLogger(__name__)


class SitemapParser:
    def __init__(self, session_factory, rate_limiter=None):
        self.session_factory = session_factory
        self.rate_limiter = rate_limiter

    async def fetch_sitemap(self, sitemap_url: str) -> list[str]:
        seen_sitemaps = set()
        seen_urls = set()
        results = []

        async def visit(url: str):
            if url in seen_sitemaps:
                return
            seen_sitemaps.add(url)
            try:
                if self.rate_limiter is not None:
                    await self.rate_limiter.acquire(urlsplit(url).netloc)
                async with self.session_factory().get(url) as response:
                    response.raise_for_status()
                    content = await response.text()
                root = ET.fromstring(content)
            except (aiohttp.ClientError, asyncio.TimeoutError, ET.ParseError) as error:
                logger.warning("Sitemap failed for %s: %s", url, error)
                return
            tag = root.tag.rsplit("}", 1)[-1]
            locations = [node.text.strip() for node in root.iter()
                         if node.tag.rsplit("}", 1)[-1] == "loc" and node.text]
            if tag == "sitemapindex":
                for child in locations:
                    await visit(urljoin(url, child))
            elif tag == "urlset":
                for child in locations:
                    address = urljoin(url, child)
                    if urlsplit(address).scheme in ("http", "https") and address not in seen_urls:
                        seen_urls.add(address)
                        results.append(address)

        await visit(sitemap_url)
        return results
