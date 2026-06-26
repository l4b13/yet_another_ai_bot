import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from aiogram.fsm.storage.redis import RedisStorage

from langchain_openai import ChatOpenAI
from redis.asyncio import Redis

from core.config import settings

from core.database import Database
from handlers.user import router as user_router
from middlewares.media_group import AlbumMiddleware
from middlewares.outer import LoggerMiddleware


logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)
logger.info("Starting bot")

if sys.platform.startswith("win") or os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command="/start",
                   description="Начать заново"),
        BotCommand(command="/help",
                   description="Справка по работе бота"),
        BotCommand(command="/profile",
                   description="Кнопочное меню"),
        BotCommand(command="/models",
                   description="Кнопочное меню"),
        BotCommand(command="/reset",
                   description="Сбросить контекст"),
        BotCommand(command="/admin",
                   description="Меню администратора (только для админов)"),
    ]
    await bot.set_my_commands(main_menu_commands)
    # await bot.set_my_description(BOT_DESCRIPTION)
    # await bot.set_my_short_description(BOT_ABOUT)


async def main():
    db_url = settings.asyncpg_url.unicode_string()
    db = Database(url=db_url)
    redis_cli = Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD, db=0
    )
    redis_storage = RedisStorage(redis_cli)

    system_llm = ChatOpenAI(
        model="gpt-5-nano",
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    dp = Dispatcher(
        storage=redis_storage,
        db=db,
        redis=redis_cli,
        system_llm=system_llm
    )

    dp.include_router(user_router)

    dp.message.outer_middleware(LoggerMiddleware())
    dp.message.outer_middleware(
        AlbumMiddleware(debounce_sec=settings.MEDIA_GROUP_DEBOUNCE_SEC)
    )
    dp.callback_query.outer_middleware(LoggerMiddleware())
    dp.startup.register(set_main_menu)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await db.create_all()
        await dp.start_polling(bot, polling_timeout=30)

    except Exception as e:
        logger.exception(e)

    finally:
        await redis_storage.close()
        await db.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
