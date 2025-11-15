from aiogram import Router
from aiogram.types import Message as TGMessage, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext


router = Router()


@router.message(Command("start"))
async def command_start(message: TGMessage, state: FSMContext):
    pass


@router.message(Command("menu"))
async def command_menu(message: TGMessage, state: FSMContext):
    pass


@router.message()
async def text_message(message: TGMessage):
    pass
