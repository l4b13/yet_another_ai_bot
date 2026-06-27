import json
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import AIModel, User
from static.categories import cat_list


class AdminMainCBF(CallbackData, prefix="adm_main"):
    pass


class AdminCloseCBF(CallbackData, prefix="adm_close"):
    pass


class AdminUsersPageCBF(CallbackData, prefix="adm_usrs"):
    page: int


class AdminUserCBF(CallbackData, prefix="adm_usr"):
    user_id: int
    page: int


class AdminUserActionCBF(CallbackData, prefix="adm_uact"):
    user_id: int
    page: int
    action: Literal["info", "balance", "premium", "config"]


class AdminModelsPageCBF(CallbackData, prefix="adm_mdls"):
    page: int


class AdminModelCBF(CallbackData, prefix="adm_mdl"):
    model_id: int
    page: int


class AdminModelActionCBF(CallbackData, prefix="adm_mact"):
    model_id: int
    page: int
    action: Literal["name", "price", "premium", "category"]


class AdminModelCatCBF(CallbackData, prefix="adm_mcat"):
    model_id: int
    page: int
    category: str


class AdminCancelFSMCBF(CallbackData, prefix="adm_cancel"):
    target: Literal["user", "model"]
    entity_id: int
    page: int


def _user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    if user.fullname:
        return user.fullname
    return f"id {user.id}"


def format_main_menu_text() -> str:
    return "*Админ-панель*\n\nВыберите раздел:"


def format_users_list_text(users: list[User], page: int) -> str:
    lines = [f"*Пользователи* (стр. {page + 1})\n"]
    if not users:
        lines.append("_Список пуст_")
    else:
        for idx, user in enumerate(users, start=1):
            lines.append(f"{idx}. {_user_label(user)} (id: {user.id})")
    return "\n".join(lines)


def format_user_card_text(user: User) -> str:
    return f"*Пользователь #{user.id}*\n\nВыберите поле:"


def format_user_config_text(user: User) -> str:
    config_json = json.dumps(user.config or {}, ensure_ascii=False, indent=2)
    if len(config_json) > 3500:
        config_json = config_json[:3500] + "\n…"
    return (
        f"*Конфиг пользователя #{user.id}* (только просмотр)\n\n"
        f"```json\n{config_json}\n```"
    )


def format_models_list_text(models: list[AIModel], page: int) -> str:
    lines = [f"*Модели* (стр. {page + 1})\n"]
    if not models:
        lines.append("_Список пуст_")
    else:
        for idx, model in enumerate(models, start=1):
            cat = model.aicategory or "—"
            lines.append(f"{idx}. {model.name} ({cat}, id: {model.id})")
    return "\n".join(lines)


def format_model_card_text(model: AIModel) -> str:
    access = "premium" if model.premium else "всем"
    cat = model.aicategory or "—"
    return (
        f"*Модель #{model.id}*\n\n"
        f"Название: `{model.name}`\n"
        f"Стоимость: `{model.price}`\n"
        f"Доступ: `{access}`\n"
        f"Категория: `{cat}`\n\n"
        "Выберите поле:"
    )


def get_main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Пользователи",
            callback_data=AdminUsersPageCBF(page=0).pack(),
        ),
        InlineKeyboardButton(
            text="Модели",
            callback_data=AdminModelsPageCBF(page=0).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="Закрыть",
            callback_data=AdminCloseCBF().pack(),
        )
    )
    return builder.as_markup()


def get_users_list_kb(
    users: list[User],
    page: int,
    *,
    has_prev: bool,
    has_next: bool,
):
    builder = InlineKeyboardBuilder()
    for idx, user in enumerate(users, start=1):
        builder.row(
            InlineKeyboardButton(
                text=f"{idx}. {_user_label(user)}",
                callback_data=AdminUserCBF(user_id=user.id, page=page).pack(),
            )
        )

    nav: list[InlineKeyboardButton] = []
    if has_prev:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=AdminUsersPageCBF(page=page - 1).pack(),
            )
        )
    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=AdminUsersPageCBF(page=page + 1).pack(),
            )
        )
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="В меню",
            callback_data=AdminMainCBF().pack(),
        )
    )
    return builder.as_markup()


def get_user_card_kb(user: User, page: int):
    premium = "да" if user.premium else "нет"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"1.1.1 {_user_label(user)}",
            callback_data=AdminUserActionCBF(
                user_id=user.id, page=page, action="info"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"1.1.2 Баланс: {user.balance}",
            callback_data=AdminUserActionCBF(
                user_id=user.id, page=page, action="balance"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"1.1.3 Премиум: {premium}",
            callback_data=AdminUserActionCBF(
                user_id=user.id, page=page, action="premium"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="1.1.4 Конфиг",
            callback_data=AdminUserActionCBF(
                user_id=user.id, page=page, action="config"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="К списку",
            callback_data=AdminUsersPageCBF(page=page).pack(),
        )
    )
    return builder.as_markup()


def get_user_config_kb(user: User, page: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="К карточке",
            callback_data=AdminUserCBF(user_id=user.id, page=page).pack(),
        )
    )
    return builder.as_markup()


def get_models_list_kb(
    models: list[AIModel],
    page: int,
    *,
    has_prev: bool,
    has_next: bool,
):
    builder = InlineKeyboardBuilder()
    for idx, model in enumerate(models, start=1):
        builder.row(
            InlineKeyboardButton(
                text=f"{idx}. {model.name}",
                callback_data=AdminModelCBF(model_id=model.id, page=page).pack(),
            )
        )

    nav: list[InlineKeyboardButton] = []
    if has_prev:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=AdminModelsPageCBF(page=page - 1).pack(),
            )
        )
    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=AdminModelsPageCBF(page=page + 1).pack(),
            )
        )
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="В меню",
            callback_data=AdminMainCBF().pack(),
        )
    )
    return builder.as_markup()


def get_model_card_kb(model: AIModel, page: int):
    access = "premium" if model.premium else "всем"
    cat = model.aicategory or "—"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"Название: {model.name}",
            callback_data=AdminModelActionCBF(
                model_id=model.id, page=page, action="name"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"Стоимость: {model.price}",
            callback_data=AdminModelActionCBF(
                model_id=model.id, page=page, action="price"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"Доступ: {access}",
            callback_data=AdminModelActionCBF(
                model_id=model.id, page=page, action="premium"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"Категория: {cat}",
            callback_data=AdminModelActionCBF(
                model_id=model.id, page=page, action="category"
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="К списку",
            callback_data=AdminModelsPageCBF(page=page).pack(),
        )
    )
    return builder.as_markup()


def get_model_category_kb(model: AIModel, page: int):
    builder = InlineKeyboardBuilder()
    for cat in cat_list:
        mark = "☑ " if model.aicategory == cat.alias else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{cat.title}",
                callback_data=AdminModelCatCBF(
                    model_id=model.id,
                    page=page,
                    category=cat.alias,
                ).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="К карточке",
            callback_data=AdminModelCBF(model_id=model.id, page=page).pack(),
        )
    )
    return builder.as_markup()


def get_cancel_fsm_kb(target: Literal["user", "model"], entity_id: int, page: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Отмена",
            callback_data=AdminCancelFSMCBF(
                target=target,
                entity_id=entity_id,
                page=page,
            ).pack(),
        )
    )
    return builder.as_markup()
