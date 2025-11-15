import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

from core.settings import settings

from bot.handlers.private import admin, user


logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=settings.TOKEN)
    dp = Dispatcher()
    dp.include_router(user.router)
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())