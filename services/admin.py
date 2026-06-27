from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AIModel, User

PAGE_SIZE = 10


class AdminService:
    @classmethod
    async def list_users(
        cls,
        db_session: AsyncSession,
        page: int,
        page_size: int = PAGE_SIZE,
    ) -> tuple[list[User], bool, bool]:
        offset = page * page_size
        query = (
            select(User)
            .order_by(User.id)
            .offset(offset)
            .limit(page_size + 1)
        )
        result = await db_session.execute(query)
        rows = list(result.scalars().all())
        has_next = len(rows) > page_size
        return rows[:page_size], page > 0, has_next

    @classmethod
    async def get_user(cls, db_session: AsyncSession, user_id: int) -> User | None:
        return await User.get_by_internal_id(db_session, user_id)

    @classmethod
    async def update_user_balance(
        cls, db_session: AsyncSession, user_id: int, balance: int
    ) -> User | None:
        user = await cls.get_user(db_session, user_id)
        if user is None:
            return None
        user.balance = balance
        await user.save(db_session)
        return user

    @classmethod
    async def toggle_user_premium(
        cls, db_session: AsyncSession, user_id: int
    ) -> User | None:
        user = await cls.get_user(db_session, user_id)
        if user is None:
            return None
        user.premium = not user.premium
        await user.save(db_session)
        return user

    @classmethod
    async def list_models(
        cls,
        db_session: AsyncSession,
        page: int,
        page_size: int = PAGE_SIZE,
    ) -> tuple[list[AIModel], bool, bool]:
        offset = page * page_size
        query = (
            select(AIModel)
            .order_by(AIModel.id)
            .offset(offset)
            .limit(page_size + 1)
        )
        result = await db_session.execute(query)
        rows = list(result.scalars().all())
        has_next = len(rows) > page_size
        return rows[:page_size], page > 0, has_next

    @classmethod
    async def get_model(cls, db_session: AsyncSession, model_id: int) -> AIModel | None:
        return await AIModel.get_by_id(db_session, model_id)

    @classmethod
    async def update_model_name(
        cls, db_session: AsyncSession, model_id: int, name: str
    ) -> AIModel | None:
        model = await cls.get_model(db_session, model_id)
        if model is None:
            return None
        model.name = name.strip()
        await model.save(db_session)
        return model

    @classmethod
    async def update_model_price(
        cls, db_session: AsyncSession, model_id: int, price: float
    ) -> AIModel | None:
        model = await cls.get_model(db_session, model_id)
        if model is None:
            return None
        model.price = price
        await model.save(db_session)
        return model

    @classmethod
    async def toggle_model_premium(
        cls, db_session: AsyncSession, model_id: int
    ) -> AIModel | None:
        model = await cls.get_model(db_session, model_id)
        if model is None:
            return None
        model.premium = not model.premium
        await model.save(db_session)
        return model

    @classmethod
    async def update_model_category(
        cls, db_session: AsyncSession, model_id: int, category: str
    ) -> AIModel | None:
        model = await cls.get_model(db_session, model_id)
        if model is None:
            return None
        model.aicategory = category
        await model.save(db_session)
        return model
