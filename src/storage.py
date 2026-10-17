import asyncio
import csv
import io
import json
from abc import ABC, abstractmethod
from pathlib import Path

import aiofiles
import aiosqlite


class DataStorage(ABC):
    @abstractmethod
    async def save(self, data: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class JSONStorage(DataStorage):
    def __init__(self, filename: str, indent: int | None = None):
        self.filename = filename
        self.indent = indent
        self._lock = asyncio.Lock()

    async def save(self, data: dict) -> None:
        line = json.dumps(data, ensure_ascii=False, default=str, indent=self.indent)
        async with self._lock:
            async with aiofiles.open(self.filename, "a", encoding="utf-8") as file:
                await file.write(line + "\n")

    async def close(self) -> None:
        pass


class CSVStorage(DataStorage):
    def __init__(self, filename: str, encoding: str = "utf-8"):
        self.filename = filename
        self.encoding = encoding
        self._lock = asyncio.Lock()
        self._fieldnames = None

    async def save(self, data: dict) -> None:
        async with self._lock:
            if self._fieldnames is None:
                path = Path(self.filename)
                if path.exists() and path.stat().st_size:
                    async with aiofiles.open(self.filename, "r", encoding=self.encoding, newline="") as file:
                        header = await file.readline()
                    self._fieldnames = next(csv.reader([header]))
                else:
                    self._fieldnames = list(data)
                    stream = io.StringIO(newline="")
                    csv.writer(stream).writerow(self._fieldnames)
                    async with aiofiles.open(self.filename, "a", encoding=self.encoding, newline="") as file:
                        await file.write(stream.getvalue())
            row = {
                key: json.dumps(data.get(key), ensure_ascii=False, default=str)
                if isinstance(data.get(key), (list, dict))
                else str(data.get(key, ""))
                for key in self._fieldnames
            }
            stream = io.StringIO(newline="")
            csv.DictWriter(stream, fieldnames=self._fieldnames).writerow(row)
            async with aiofiles.open(self.filename, "a", encoding=self.encoding, newline="") as file:
                await file.write(stream.getvalue())

    async def close(self) -> None:
        pass


class SQLiteStorage(DataStorage):
    def __init__(self, filename: str, batch_size: int = 20):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.filename = filename
        self.batch_size = batch_size
        self.connection = None
        self._pending = []
        self._lock = asyncio.Lock()

    async def init_db(self) -> None:
        if self.connection is None:
            self.connection = await aiosqlite.connect(self.filename)
            await self.connection.execute(
                "CREATE TABLE IF NOT EXISTS pages ("
                "url TEXT PRIMARY KEY, title TEXT, text TEXT, links TEXT, "
                "metadata TEXT, crawled_at TEXT, status_code INTEGER, content_type TEXT)"
            )
            await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_pages_time ON pages(crawled_at)")
            await self.connection.commit()

    async def _flush(self) -> None:
        if self._pending:
            await self.connection.executemany(
                "INSERT OR REPLACE INTO pages "
                "(url, title, text, links, metadata, crawled_at, status_code, content_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                self._pending,
            )
            await self.connection.commit()
            self._pending.clear()

    async def save(self, data: dict) -> None:
        async with self._lock:
            await self.init_db()
            self._pending.append((
                data["url"], data.get("title", ""), data.get("text", ""),
                json.dumps(data.get("links", []), ensure_ascii=False),
                json.dumps(data.get("metadata", {}), ensure_ascii=False),
                str(data.get("crawled_at", "")), data.get("status_code"),
                data.get("content_type", ""),
            ))
            if len(self._pending) >= self.batch_size:
                await self._flush()

    async def close(self) -> None:
        async with self._lock:
            if self.connection is not None:
                try:
                    await self._flush()
                finally:
                    await self.connection.close()
                    self.connection = None
