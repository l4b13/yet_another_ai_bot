from sqlalchemy.ext.asyncio import AsyncSession
from models import AIModel
from static.categories import (
    cat_list, AICategory
)


class AIService:
    @classmethod
    async def get_categories(
        cls, db_session: AsyncSession
    ) -> list[AICategory]:
        _ = db_session
        return list(cat_list)

    @classmethod
    async def get_models(cls, db_session: AsyncSession, cat: str):
        return await AIModel.get_by_cat(db_session, cat)

    @classmethod
    async def get_model(
        cls, db_session: AsyncSession, model_id: int | None = None
    ):
        return await AIModel.get_by_id(db_session, model_id)

    @classmethod
    async def get_user_models(
        cls, db_session: AsyncSession, config: dict | None
    ) -> dict[str, AIModel | None]:
        result: dict[str, AIModel | None] = {}
        cfg = config or {}

        for cat in cat_list:
            mid = cfg.get(f"{cat.alias}_model_id")
            model = await cls.get_model(db_session, mid)
            result[cat.alias] = model

        return result
