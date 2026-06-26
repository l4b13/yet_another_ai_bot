import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base

if TYPE_CHECKING:
    from . import User, Message


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation"
    )

    @classmethod
    async def get_last(cls, db_session: AsyncSession, user_id: int):
        query = select(cls).where(cls.user_id == user_id).order_by(
            cls.created_at.desc()
        ).limit(1)
        result = await db_session.execute(query)
        return result.scalars().first()


__all__ = ['Conversation']
