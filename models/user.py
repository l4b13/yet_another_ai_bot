from typing import TYPE_CHECKING
from sqlalchemy import JSON, String, Integer, select, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base

if TYPE_CHECKING:
    from . import Conversation


ai_config = {
    "text_model_id": None,
    "image_model_id": None,
    "audio_model_id": None,
    "video_model_id": None,
    "temperature": None
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, nullable=True)
    fullname: Mapped[str] = mapped_column(String, nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    premium: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=True, default=False
    )
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        default=ai_config
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user")

    @classmethod
    async def get_one(
        cls, db_session: AsyncSession, chat_id: int
    ):
        query = select(cls).where(cls.chat_id == str(chat_id))

        result = await db_session.execute(query)
        return result.scalars().first()

    def update_config(self, data: dict = None, **kwargs):
        if self.config is None:
            self.config = dict(ai_config)

        if data:
            self.config.update(data)

        if kwargs:
            self.config.update(kwargs)

        flag_modified(self, "config")


__all__ = ['User']
