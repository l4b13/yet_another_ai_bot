import logging

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from core.database import Database
from filters.chat_type import ChatTypeFilter
from filters.is_admin import IsAdminFilter
from keyboards.admin import (
    AdminCancelFSMCBF,
    AdminCloseCBF,
    AdminMainCBF,
    AdminModelActionCBF,
    AdminModelCBF,
    AdminModelCatCBF,
    AdminModelsPageCBF,
    AdminUserActionCBF,
    AdminUserCBF,
    AdminUsersPageCBF,
    format_main_menu_text,
    format_model_card_text,
    format_models_list_text,
    format_user_card_text,
    format_user_config_text,
    format_users_list_text,
    get_cancel_fsm_kb,
    get_main_menu_kb,
    get_model_card_kb,
    get_model_category_kb,
    get_models_list_kb,
    get_user_card_kb,
    get_user_config_kb,
    get_users_list_kb,
)
from services.admin import AdminService
from static.texts import PRIVATE
from states.user import AdminStates

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(ChatTypeFilter(chat_type=PRIVATE))
router.callback_query.filter(ChatTypeFilter(chat_type=PRIVATE))

ADMIN_PARSE_MODE = None


async def _show_main_menu(message: types.Message):
    await message.answer(
        format_main_menu_text(),
        reply_markup=get_main_menu_kb(),
        parse_mode=ADMIN_PARSE_MODE,
    )


async def _edit_main_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        format_main_menu_text(),
        reply_markup=get_main_menu_kb(),
        parse_mode=ADMIN_PARSE_MODE,
    )


async def _edit_users_page(
    callback: types.CallbackQuery, db: Database, page: int
):
    async with db.get_session() as db_session:
        users, has_prev, has_next = await AdminService.list_users(
            db_session, page
        )
    await callback.message.edit_text(
        format_users_list_text(users, page),
        reply_markup=get_users_list_kb(
            users, page, has_prev=has_prev, has_next=has_next
        ),
        parse_mode=ADMIN_PARSE_MODE,
    )


async def _edit_user_card(
    callback: types.CallbackQuery, db: Database, user_id: int, page: int
):
    async with db.get_session() as db_session:
        user = await AdminService.get_user(db_session, user_id)
    if user is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        await _edit_users_page(callback, db, page)
        return
    await callback.message.edit_text(
        format_user_card_text(user),
        reply_markup=get_user_card_kb(user, page),
        parse_mode=ADMIN_PARSE_MODE,
    )


async def _edit_models_page(
    callback: types.CallbackQuery, db: Database, page: int
):
    async with db.get_session() as db_session:
        models, has_prev, has_next = await AdminService.list_models(
            db_session, page
        )
    await callback.message.edit_text(
        format_models_list_text(models, page),
        reply_markup=get_models_list_kb(
            models, page, has_prev=has_prev, has_next=has_next
        ),
        parse_mode=ADMIN_PARSE_MODE,
    )


async def _edit_model_card(
    callback: types.CallbackQuery, db: Database, model_id: int, page: int
):
    async with db.get_session() as db_session:
        model = await AdminService.get_model(db_session, model_id)
    if model is None:
        await callback.answer("Модель не найдена", show_alert=True)
        await _edit_models_page(callback, db, page)
        return
    await callback.message.edit_text(
        format_model_card_text(model),
        reply_markup=get_model_card_kb(model, page),
        parse_mode=ADMIN_PARSE_MODE,
    )


@router.message(Command(commands="admin"), IsAdminFilter())
async def admin_command(message: types.Message, state: FSMContext):
    await state.clear()
    await _show_main_menu(message)


@router.message(Command(commands="admin"))
async def admin_denied(message: types.Message):
    await message.delete()


@router.callback_query(AdminCloseCBF.filter(), IsAdminFilter())
async def admin_close(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(AdminMainCBF.filter(), IsAdminFilter())
async def admin_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _edit_main_menu(callback)


@router.callback_query(AdminUsersPageCBF.filter(), IsAdminFilter())
async def admin_users_page(
    callback: types.CallbackQuery,
    callback_data: AdminUsersPageCBF,
    db: Database,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()
    await _edit_users_page(callback, db, callback_data.page)


@router.callback_query(AdminUserCBF.filter(), IsAdminFilter())
async def admin_user_card(
    callback: types.CallbackQuery,
    callback_data: AdminUserCBF,
    db: Database,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()
    await _edit_user_card(callback, db, callback_data.user_id, callback_data.page)


@router.callback_query(AdminUserActionCBF.filter(), IsAdminFilter())
async def admin_user_action(
    callback: types.CallbackQuery,
    callback_data: AdminUserActionCBF,
    db: Database,
    state: FSMContext,
):
    async with db.get_session() as db_session:
        user = await AdminService.get_user(db_session, callback_data.user_id)

    if user is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    action = callback_data.action
    page = callback_data.page

    if action == "premium":
        async with db.get_session() as db_session:
            user = await AdminService.toggle_user_premium(
                db_session, callback_data.user_id
            )
        await callback.answer("Премиум обновлён")
        if user:
            await callback.message.edit_text(
                format_user_card_text(user),
                reply_markup=get_user_card_kb(user, page),
                parse_mode=ADMIN_PARSE_MODE,
            )
        return

    if action == "config":
        await callback.answer()
        async with db.get_session() as db_session:
            display_config = await AdminService.config_for_display(
                db_session, user.config
            )
        await callback.message.edit_text(
            format_user_config_text(user, display_config),
            reply_markup=get_user_config_kb(user, page),
            parse_mode=ADMIN_PARSE_MODE,
        )
        return

    if action == "balance":
        await callback.answer()
        await state.set_state(AdminStates.edit_user_balance)
        await state.update_data(
            user_id=callback_data.user_id,
            page=page,
            menu_message_id=callback.message.message_id,
        )
        await callback.message.edit_text(
            f"Пользователь #{user.id}\n\n"
            f"Текущий баланс: {user.balance}\n"
            "Введите новое целое число:",
            reply_markup=get_cancel_fsm_kb("user", user.id, page),
            parse_mode=ADMIN_PARSE_MODE,
        )


@router.callback_query(AdminModelsPageCBF.filter(), IsAdminFilter())
async def admin_models_page(
    callback: types.CallbackQuery,
    callback_data: AdminModelsPageCBF,
    db: Database,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()
    await _edit_models_page(callback, db, callback_data.page)


@router.callback_query(AdminModelCBF.filter(), IsAdminFilter())
async def admin_model_card(
    callback: types.CallbackQuery,
    callback_data: AdminModelCBF,
    db: Database,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()
    await _edit_model_card(
        callback, db, callback_data.model_id, callback_data.page
    )


@router.callback_query(AdminModelActionCBF.filter(), IsAdminFilter())
async def admin_model_action(
    callback: types.CallbackQuery,
    callback_data: AdminModelActionCBF,
    db: Database,
    state: FSMContext,
):
    async with db.get_session() as db_session:
        model = await AdminService.get_model(db_session, callback_data.model_id)

    if model is None:
        await callback.answer("Модель не найдена", show_alert=True)
        return

    action = callback_data.action
    page = callback_data.page

    if action == "premium":
        async with db.get_session() as db_session:
            model = await AdminService.toggle_model_premium(
                db_session, callback_data.model_id
            )
        await callback.answer("Доступ обновлён")
        if model:
            await callback.message.edit_text(
                format_model_card_text(model),
                reply_markup=get_model_card_kb(model, page),
                parse_mode=ADMIN_PARSE_MODE,
            )
        return

    if action == "category":
        await callback.answer()
        await callback.message.edit_text(
            f"Модель #{model.id}\n\nВыберите категорию:",
            reply_markup=get_model_category_kb(model, page),
            parse_mode=ADMIN_PARSE_MODE,
        )
        return

    await callback.answer()
    await state.update_data(
        model_id=callback_data.model_id,
        page=page,
        menu_message_id=callback.message.message_id,
    )

    if action == "name":
        await state.set_state(AdminStates.edit_model_name)
        await callback.message.edit_text(
            f"Модель #{model.id}\n\n"
            f"Текущее название: {model.name}\n"
            "Введите новое название:",
            reply_markup=get_cancel_fsm_kb("model", model.id, page),
            parse_mode=ADMIN_PARSE_MODE,
        )
        return

    if action == "price":
        await state.set_state(AdminStates.edit_model_price)
        await callback.message.edit_text(
            f"Модель #{model.id}\n\n"
            f"Текущая стоимость: {model.price}\n"
            "Введите новое число:",
            reply_markup=get_cancel_fsm_kb("model", model.id, page),
            parse_mode=ADMIN_PARSE_MODE,
        )


@router.callback_query(AdminModelCatCBF.filter(), IsAdminFilter())
async def admin_model_category(
    callback: types.CallbackQuery,
    callback_data: AdminModelCatCBF,
    db: Database,
):
    async with db.get_session() as db_session:
        model = await AdminService.update_model_category(
            db_session,
            callback_data.model_id,
            callback_data.category,
        )
    if model is None:
        await callback.answer("Модель не найдена", show_alert=True)
        return
    await callback.answer("Категория сохранена")
    await callback.message.edit_text(
        format_model_card_text(model),
        reply_markup=get_model_card_kb(model, callback_data.page),
        parse_mode=ADMIN_PARSE_MODE,
    )


@router.callback_query(AdminCancelFSMCBF.filter(), IsAdminFilter())
async def admin_cancel_fsm(
    callback: types.CallbackQuery,
    callback_data: AdminCancelFSMCBF,
    db: Database,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()
    if callback_data.target == "user":
        await _edit_user_card(
            callback, db, callback_data.entity_id, callback_data.page
        )
    else:
        await _edit_model_card(
            callback, db, callback_data.entity_id, callback_data.page
        )


@router.message(StateFilter(AdminStates.edit_user_balance), IsAdminFilter())
async def admin_save_user_balance(
    message: types.Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
):
    data = await state.get_data()
    user_id = data.get("user_id")
    page = data.get("page", 0)
    menu_message_id = data.get("menu_message_id")

    text = (message.text or "").strip()
    try:
        balance = int(text)
    except ValueError:
        await message.answer("Введите целое число или нажмите «Отмена».", parse_mode=ADMIN_PARSE_MODE)
        return

    async with db.get_session() as db_session:
        user = await AdminService.update_user_balance(db_session, user_id, balance)

    await state.clear()

    if user is None:
        await message.answer("Пользователь не найден.", parse_mode=ADMIN_PARSE_MODE)
        return

    card_text = format_user_card_text(user)
    card_kb = get_user_card_kb(user, page)
    if menu_message_id:
        try:
            await bot.edit_message_text(
                card_text,
                chat_id=message.chat.id,
                message_id=menu_message_id,
                reply_markup=card_kb,
                parse_mode=ADMIN_PARSE_MODE,
            )
        except Exception:
            await message.answer(
                card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
            )
    else:
        await message.answer(
            card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
        )

    await message.answer(
        f"Баланс обновлён: {balance}", parse_mode=ADMIN_PARSE_MODE
    )


@router.message(StateFilter(AdminStates.edit_model_name), IsAdminFilter())
async def admin_save_model_name(
    message: types.Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
):
    data = await state.get_data()
    model_id = data.get("model_id")
    page = data.get("page", 0)
    menu_message_id = data.get("menu_message_id")

    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым.", parse_mode=ADMIN_PARSE_MODE)
        return

    async with db.get_session() as db_session:
        model = await AdminService.update_model_name(db_session, model_id, name)

    await state.clear()

    if model is None:
        await message.answer("Модель не найдена.", parse_mode=ADMIN_PARSE_MODE)
        return

    card_text = format_model_card_text(model)
    card_kb = get_model_card_kb(model, page)
    if menu_message_id:
        try:
            await bot.edit_message_text(
                card_text,
                chat_id=message.chat.id,
                message_id=menu_message_id,
                reply_markup=card_kb,
                parse_mode=ADMIN_PARSE_MODE,
            )
        except Exception:
            await message.answer(
                card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
            )
    else:
        await message.answer(
            card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
        )

    await message.answer(
        f"Название обновлено: {model.name}", parse_mode=ADMIN_PARSE_MODE
    )


@router.message(StateFilter(AdminStates.edit_model_price), IsAdminFilter())
async def admin_save_model_price(
    message: types.Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
):
    data = await state.get_data()
    model_id = data.get("model_id")
    page = data.get("page", 0)
    menu_message_id = data.get("menu_message_id")

    text = (message.text or "").strip().replace(",", ".")
    try:
        price = float(text)
    except ValueError:
        await message.answer("Введите число или нажмите «Отмена».", parse_mode=ADMIN_PARSE_MODE)
        return

    async with db.get_session() as db_session:
        model = await AdminService.update_model_price(db_session, model_id, price)

    await state.clear()

    if model is None:
        await message.answer("Модель не найдена.", parse_mode=ADMIN_PARSE_MODE)
        return

    card_text = format_model_card_text(model)
    card_kb = get_model_card_kb(model, page)
    if menu_message_id:
        try:
            await bot.edit_message_text(
                card_text,
                chat_id=message.chat.id,
                message_id=menu_message_id,
                reply_markup=card_kb,
                parse_mode=ADMIN_PARSE_MODE,
            )
        except Exception:
            await message.answer(
                card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
            )
    else:
        await message.answer(
            card_text, reply_markup=card_kb, parse_mode=ADMIN_PARSE_MODE
        )

    await message.answer(
        f"Стоимость обновлена: {model.price}", parse_mode=ADMIN_PARSE_MODE
    )
