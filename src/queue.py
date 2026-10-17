import asyncio
import itertools


class CrawlerQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._counter = itertools.count()
        self._depths = {}
        self._seen = set()
        self.processed = set()
        self.failed = {}

    def add_url(self, url: str, priority: int = 0, depth: int = 0) -> bool:
        if url in self._seen:
            return False
        self._seen.add(url)
        self._depths[url] = depth
        self._queue.put_nowait((priority, next(self._counter), url))
        return True

    async def get_next(self) -> str | None:
        _, _, url = await self._queue.get()
        return url

    def depth_for(self, url: str) -> int:
        return self._depths[url]

    def mark_processed(self, url: str) -> None:
        self.processed.add(url)
        self._queue.task_done()

    def mark_failed(self, url: str, error: str) -> None:
        self.failed[url] = error
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    def get_stats(self) -> dict:
        return {
            "queued": self._queue.qsize(),
            "discovered": len(self._seen),
            "processed": len(self.processed),
            "failed": len(self.failed),
        }
