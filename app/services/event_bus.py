"""In-memory pub/sub for document processing SSE events (single-server dev)."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

TERMINAL_STATUSES = frozenset({"completed", "failed"})


class DocumentEventBus:
    """Broadcast status events to open SSE connections for a document."""

    def __init__(self) -> None:
        self._queues: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, document_id: UUID, event: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._queues.get(document_id, []))

        for queue in queues:
            await queue.put(event)

    async def subscribe(self, document_id: UUID) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._queues[document_id].append(queue)

        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("status") in TERMINAL_STATUSES:
                    break
        finally:
            async with self._lock:
                self._queues[document_id] = [
                    existing for existing in self._queues[document_id] if existing is not queue
                ]
                if not self._queues[document_id]:
                    del self._queues[document_id]


document_event_bus = DocumentEventBus()
