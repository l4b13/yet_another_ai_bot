from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_type: Union[str, list]):
        self.chat_type = chat_type

    async def __call__(self, update: Message | CallbackQuery) -> bool:
        if isinstance(update, Message):
            if isinstance(self.chat_type, str):
                return update.chat.type == self.chat_type
            else:
                return update.chat.type in self.chat_type
        if isinstance(update, CallbackQuery):
            if isinstance(self.chat_type, str):
                return update.message.chat.type == self.chat_type
            else:
                return update.message.chat.type in self.chat_type
