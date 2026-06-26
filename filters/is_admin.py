from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from core.database import Database
from models.user import User


class IsAdminFilter(BaseFilter):
    def __init__(self):
        pass

    async def __call__(
        self, update: Message | CallbackQuery, db: Database
    ) -> bool:
        chat_id = update.from_user.id
        async with db.get_session() as db_session:
            user = await User.get_one(db_session, chat_id)
        if user is not None:
            return True
        return False
