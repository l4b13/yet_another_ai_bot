import logging

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
    AsyncSession
)

from models.base import Base


logger = logging.getLogger(__file__)


class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(
            url=url, future=True, echo=False)
        self.AsyncSessionFactory = async_sessionmaker(
            self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    async def create_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def dispose(self):
        await self.engine.dispose()

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        async with self.AsyncSessionFactory() as session:
            # logger.debug(f"ASYNC Pool: {engine.pool.status()}")
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error getting database session: {e}")
                raise
            finally:
                await session.close()
