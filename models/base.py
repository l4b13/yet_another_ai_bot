from typing import Any

from asyncpg import UniqueViolationError
import logging
from sqlalchemy import select, func, DateTime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid import UUID
from datetime import datetime as dt


logger = logging.getLogger(__name__)


class Base(AsyncAttrs, DeclarativeBase):
    id: Any
    created_at: Mapped[dt] = mapped_column(
        DateTime, server_default=func.now())
    updated_at: Mapped[dt] = mapped_column(
        DateTime, server_default=func.now(), server_onupdate=func.now())
    __name__: str

    @classmethod
    async def get_by_id(cls, db_session: AsyncSession, id: int | UUID):
        return await db_session.get(cls, id)

    @classmethod
    async def get_all(cls, db_session: AsyncSession):
        query = select(cls).order_by(cls.id)
        result = await db_session.execute(query)
        return result.scalars().all()

    async def save(self, db_session: AsyncSession):
        """

        :param db_session:
        :return:
        """
        try:
            db_session.add(self)
            await db_session.commit()
            await db_session.refresh(self)
            return self
        except SQLAlchemyError as ex:
            logger.error(f"Error saving {self.__class__.__name__}: {ex}")
            await db_session.rollback()
            raise

    async def delete(self, db_session: AsyncSession):
        """

        :param db_session:
        :return:
        """
        try:
            await db_session.delete(self)
            await db_session.commit()
            return True
        except SQLAlchemyError as ex:
            logger.error(f"Error deleting {self.__class__.__name__}: {ex}")
            await db_session.rollback()
            raise

    async def update(self, db_session: AsyncSession, **kwargs):
        """

        :param db:
        :param kwargs:
        :return:
        """
        try:
            for k, v in kwargs.items():
                setattr(self, k, v)
            await db_session.commit()
            await db_session.refresh(self)
            return self
        except SQLAlchemyError as ex:
            logger.error(f"Error updating {self.__class__.__name__}: {ex}")
            await db_session.rollback()
            raise

    async def save_or_update(self, db_session: AsyncSession):
        try:
            db_session.add(self)
            await db_session.commit()
            await db_session.refresh(self)
            return self
        except IntegrityError as ex:
            await db_session.rollback()
            if isinstance(ex.orig, UniqueViolationError):
                return await db_session.merge(self)
            logger.error(
                f"Error in save_or_update {self.__class__.__name__}: {ex}"
            )
            raise
        except SQLAlchemyError as ex:
            logger.error(
                f"Error in save_or_update {self.__class__.__name__}: {ex}"
            )
            await db_session.rollback()
            raise


__all__ = ['Base']
