from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, String, ForeignKey, select, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from . import Conversation


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)

    text: Mapped[str] = mapped_column(String)
    is_bot: Mapped[bool] = mapped_column(Boolean)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=True)

    tokens: Mapped[int] = mapped_column(Integer, nullable=True)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"))

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages")

    @classmethod
    async def get_many(
        cls, db_session: AsyncSession, conversation_id: uuid.UUID,
        limit: int = None
    ):
        query = (
            select(cls)
            .where(cls.conversation_id == conversation_id)
            .order_by(cls.created_at.desc())
        )

        if limit:
            query = query.limit(limit)

        result = await db_session.execute(query)
        return result.scalars().all()


__all__ = ['Message']
