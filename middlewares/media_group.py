import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class AlbumMiddleware(BaseMiddleware):
    """
    Собирает фото из одного media_group (альбом) и отдаёт в хендлер одним вызовом.
    Промежуточные апдейты не доходят до роутера; после паузы debounce вызывается
    handler один раз с data["album_messages"].
    """

    def __init__(self, debounce_sec: float = 0.85, max_photos: int = 10) -> None:
        self.debounce_sec = debounce_sec
        self.max_photos = max_photos
        self._lock = asyncio.Lock()
        self._buffers: dict[tuple[int, str], list[Message]] = {}
        self._latest_data: dict[tuple[int, str], dict[str, Any]] = {}
        self._tasks: dict[tuple[int, str], asyncio.Task[None]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if event.media_group_id is None or not event.photo:
            return await handler(event, data)

        key = (event.chat.id, str(event.media_group_id))

        async with self._lock:
            self._buffers.setdefault(key, []).append(event)
            self._latest_data[key] = data

            old_task = self._tasks.pop(key, None)
            if old_task is not None:
                old_task.cancel()

            self._tasks[key] = asyncio.create_task(
                self._flush_after_debounce(key, handler)
            )

        return None

    async def _flush_after_debounce(
        self,
        key: tuple[int, str],
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
    ) -> None:
        try:
            await asyncio.sleep(self.debounce_sec)
        except asyncio.CancelledError:
            return

        async with self._lock:
            raw = self._buffers.pop(key, [])
            base_data = self._latest_data.pop(key, {})
            self._tasks.pop(key, None)

        if not raw:
            return

        raw.sort(key=lambda m: m.message_id)
        photo_msgs = [m for m in raw if m.photo][: self.max_photos]
        if not photo_msgs:
            return

        anchor = photo_msgs[-1]
        merged = {**base_data, "album_messages": photo_msgs}

        try:
            await handler(anchor, merged)
        except Exception:
            logger.exception("Album handler failed for chat=%s group=%s", key[0], key[1])
