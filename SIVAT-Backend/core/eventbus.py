import asyncio
from typing import Any, Dict, Set


class EventBroadcaster:
    """
    Bus de eventos en memoria para difundir noticias/rumores nuevos a todos los
    clientes conectados (Server-Sent Events) en cuanto se ingieren, sin esperar
    a que el periodista recargue la página.
    """

    def __init__(self) -> None:
        self._subscribers: Set["asyncio.Queue[Dict[str, Any]]"] = set()

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subscribers.discard(queue)

    async def publish(self, evento: Dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            await queue.put(evento)


# Bus dedicado a las noticias/rumores internacionales (GDELT, X, YouTube)
internacionales_bus = EventBroadcaster()
