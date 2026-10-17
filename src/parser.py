import logging
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class HTMLParser:
    async def parse_html(self, html: str, url: str) -> dict:
        result = {
            "url": url,
            "title": "",
            "text": "",
            "links": [],
            "metadata": {},
            "images": [],
            "headings": [],
            "tables": [],
            "lists": [],
        }
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as error:
            logger.warning("HTML parser error for %s: %s", url, error)
            return result
        extractors = {
            "metadata": lambda: self.extract_metadata(soup),
            "links": lambda: self.extract_links(soup, url),
            "images": lambda: self.extract_images(soup, url),
            "headings": lambda: self.extract_headings(soup),
            "tables": lambda: self.extract_tables(soup),
            "lists": lambda: self.extract_lists(soup),
            "text": lambda: self.extract_text(soup),
        }
        for field, extract in extractors.items():
            try:
                result[field] = extract()
            except Exception as error:
                logger.warning("Error extracting %s from %s: %s", field, url, error)
        result["title"] = result["metadata"].get("title", "")
        return result

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links = []
        seen = set()
        for element in soup.select("a[href]"):
            href = element.get("href", "").strip()
            url = urldefrag(urljoin(base_url, href)).url
            if urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).netloc:
                continue
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    def extract_text(self, soup: BeautifulSoup, selector: str = None) -> str:
        element = soup.select_one(selector) if selector else soup.select_one("main") or soup.body or soup
        if element is None:
            return ""
        clean = BeautifulSoup(str(element), "lxml")
        for tag in clean.select("script, style, noscript"):
            tag.decompose()
        return clean.get_text(" ", strip=True)

    def extract_metadata(self, soup: BeautifulSoup) -> dict:
        metadata = {"title": soup.title.get_text(" ", strip=True) if soup.title else ""}
        for name in ("description", "keywords"):
            tag = soup.find("meta", attrs={"name": name})
            metadata[name] = tag.get("content", "") if tag else ""
        return metadata

    def extract_images(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        images = []
        for tag in soup.select("img[src]"):
            src = urljoin(base_url, tag["src"])
            if urlsplit(src).scheme in {"http", "https"} and urlsplit(src).netloc:
                images.append({"src": src, "alt": tag.get("alt", "")})
        return images

    def extract_headings(self, soup: BeautifulSoup) -> list[dict]:
        return [
            {"tag": tag.name, "text": tag.get_text(" ", strip=True)}
            for tag in soup.select("h1, h2, h3")
        ]

    def extract_tables(self, soup: BeautifulSoup) -> list[list[list[str]]]:
        return [
            [[cell.get_text(" ", strip=True) for cell in row.select("th, td")]
             for row in table.select("tr")]
            for table in soup.select("table")
        ]

    def extract_lists(self, soup: BeautifulSoup) -> list[dict]:
        return [
            {"type": tag.name, "items": [item.get_text(" ", strip=True)
                                       for item in tag.find_all("li", recursive=False)]}
            for tag in soup.select("ul, ol")
        ]
