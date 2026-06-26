import logging
from pathlib import Path
from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from core.config import settings


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

Path(settings.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(settings.LOG_FILE)
file_handler.setLevel(settings.LOG_LEVEL)

formatter = logging.Formatter(settings.LOG_FORMAT)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

log_message = "[m] - {username} ({chat_id}): {text}"
log_callback = "[c] - {username} ({chat_id}): {data}"


class LoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            preview = event.text or event.caption
            if preview is None and event.photo:
                preview = "[photo]"
            logger.info(log_message.format(
                username=event.from_user.username,
                chat_id=event.chat.id,
                text=preview or "",
            ))
        elif isinstance(event, CallbackQuery):
            logger.info(log_callback.format(
                username=event.from_user.username,
                chat_id=event.message.chat.id,
                data=event.data
            ))
        return await handler(event, data)
