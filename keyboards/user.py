from aiogram.types import (
    # KeyboardButton,
    # ReplyKeyboardMarkup,
    # ReplyKeyboardRemove,
    InlineKeyboardButton,
    # InlineKeyboardMarkup
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
    # ReplyKeyboardBuilder
)
from aiogram.filters.callback_data import CallbackData
from models import AIModel
from static.categories import AICategory


class MenuCloseCBF(CallbackData, prefix="menu_close"):
    pass


class AIMainCBF(CallbackData, prefix="ai_main"):
    pass


class AICategoryCBF(CallbackData, prefix="ai_cat"):
    cat_id: int


class AIModelCBF(CallbackData, prefix="ai_model"):
    cat_id: int
    model_id: int


def get_inline_cats_kb(cats: list[AICategory]):
    builder = InlineKeyboardBuilder()
    for cat in cats:
        cat_button = InlineKeyboardButton(
            text=cat.title,
            callback_data=AICategoryCBF(
                cat_id=cat.id
            ).pack()
        )
        builder.row(cat_button)
    close_button = InlineKeyboardButton(
        text="Закрыть",
        callback_data=MenuCloseCBF().pack()
    )
    builder.row(close_button)
    return builder.as_markup()


def get_inline_models_kb(
    cat_id: int, models: list[AIModel], chosen_model_id: int | None = None
):
    builder = InlineKeyboardBuilder()
    for model in models:
        text = model.name
        if model.id == chosen_model_id:
            text = f"☑ {text}"
        model_button = InlineKeyboardButton(
            text=text,
            callback_data=AIModelCBF(
                cat_id=cat_id,
                model_id=model.id
            ).pack()
        )
        builder.row(model_button)
    back_button = InlineKeyboardButton(
        text="Назад",
        callback_data=AIMainCBF().pack()
    )
    builder.row(back_button)
    close_button = InlineKeyboardButton(
        text="Закрыть",
        callback_data=MenuCloseCBF().pack()
    )
    builder.row(close_button)
    return builder.as_markup()
