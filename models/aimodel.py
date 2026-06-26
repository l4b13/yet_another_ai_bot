from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base

if TYPE_CHECKING:
    from . import User


class AIModel(Base):
    __tablename__ = "aimodels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    premium: Mapped[bool] = mapped_column(Boolean, default=False)

    aicategory: Mapped[str] = mapped_column(String, nullable=True)

    @classmethod
    async def get_by_cat(cls, db_session: AsyncSession, cat: str):
        query = select(cls).where(cls.aicategory == cat)
        result = await db_session.execute(query)
        return result.scalars().all()

    @classmethod
    async def get_by_id(cls, db_session: AsyncSession, model_id: int | None):
        if model_id is None:
            return None
        return await db_session.get(cls, model_id)


__all__ = ["AIModel"]
