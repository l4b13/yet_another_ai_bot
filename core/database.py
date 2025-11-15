from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, DateTime, select, update, delete, func, funcfilter
from typing import List, Optional, TypeVar, Type, Any, Dict
from datetime import datetime
import uuid


class BaseModel:
    id: Any
    created_at = Column(
        DateTime,
        server_default=datetime.now()
    )
    updated_at = Column(
        DateTime,
        server_default=datetime.now(),
        server_onupdate=datetime.now()
    )
    
    @classmethod
    async def save(cls, db: AsyncSession):
        db.add(cls)
        await db.commit()
        await db.refresh(cls)
        return cls
    
    @classmethod
    async def get(cls, db: AsyncSession, id: Any):
        return await db.get(cls, id)
    
    @classmethod
    async def get_all(
        cls, db: AsyncSession, skip: int = 0, limit: int = 100,
        order_by: str | None = None
    ):
        query = select(cls)
        
        if order_by:
            if order_by.startswith('-'):
                field: Column = getattr(cls, order_by[1:])
                query = query.order_by(field.desc())
            else:
                field: Column = getattr(cls, order_by)
                query = query.order_by(field)
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def filter(cls, db: AsyncSession, **filters: Any):
        query = select(cls)
        for field, value in filters.items():
            if hasattr(cls, field):
                query = query.where(getattr(cls, field) == value)
        result = await db.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def first(cls, db: AsyncSession, **filters: Any):
        query = select(cls)
        for field, value in filters.items():
            if hasattr(cls, field):
                query = query.where(getattr(cls, field) == value)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def update(self, db: AsyncSession, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        await db.commit()
        await db.refresh(self)
    
    @classmethod
    async def bulk_update(
        cls, 
        db: AsyncSession, 
        filters: Dict[str, Any], 
        updates: Dict[str, Any]
    ) -> int:
        query = update(cls).where(*[
            getattr(cls, field) == value for field, value in filters.items()
        ]).values(**updates)
        
        result = await db.execute(query)
        await db.commit()
        return result.fetchall().count()
    
    async def delete(self, db: AsyncSession) -> None:
        await db.delete(self)
        await db.commit()
    
    @classmethod
    async def delete_by_id(cls, db: AsyncSession, id: Any) -> bool:
        instance = await db.get(cls, id)
        if instance:
            await db.delete(instance)
            await db.commit()
            return True
        return False
    
    @classmethod
    async def bulk_delete(cls, db: AsyncSession, **filters: Any) -> int:
        query = delete(cls)
        for field, value in filters.items():
            if hasattr(cls, field):
                query = query.where(getattr(cls, field) == value)
        
        result = await db.execute(query)
        await db.commit()
        return result.fetchall().count()
    
    @classmethod
    async def count(cls, db: AsyncSession, **filters: Any) -> int:
        query = select(cls)
        for field, value in filters.items():
            if hasattr(cls, field):
                query = query.where(getattr(cls, field) == value)
        result = await db.execute(
            select(func.count()).select_from(query.subquery()))
        return result
    
    @classmethod
    def exists(cls, db: AsyncSession, **filters: Any):
        return cls.count(db, **filters) > 0
    
    @classmethod
    async def create_bulk(cls, db: AsyncSession, data_list: List[Dict[str, Any]]):
        instances = [cls(**data) for data in data_list]
        db.add_all(instances)
        db.commit()
        
        for instance in instances:
            db.refresh(instance)
        
        return instances
