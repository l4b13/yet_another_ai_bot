import asyncio
import logging
from pathlib import Path
from typing import Any

from aiogram import F, Bot, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.utils.formatting import Text
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from core.database import Database
from core.config import settings
from models import Message
from services.chat import ChatService
from services.ai import AIService
from services.graph import GraphState, graph_builder, message_text
from services.telegram_media import (
    album_user_text,
    download_album_photos_as_base64,
    download_message_video_frames_as_base64,
    message_has_video,
)
from static.texts import (
    PRIVATE, START_RESPONSE, HELP_RESPONSE, PROFILE_RESPONSE, RESET_RESPONSE
)

from filters.chat_type import ChatTypeFilter
from keyboards.user import (
    AIMainCBF, AICategoryCBF, AIModelCBF, MenuCloseCBF,
    get_inline_cats_kb, get_inline_models_kb
)
from static.categories import cat_list
# from states.user import AdminStates


Path("./data/logs").mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
error_handler = logging.FileHandler("./data/logs/error_telegram.log")
error_handler.setLevel(logging.ERROR)
formatter = logging.Formatter(settings.LOG_FORMAT)
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

router = Router()
router.message.filter(ChatTypeFilter(chat_type=PRIVATE))
router.callback_query.filter(ChatTypeFilter(chat_type=PRIVATE))


@router.message(CommandStart())
async def process_start_command(
    message: types.Message, state: FSMContext, db: Database
):
    async with db.get_session() as db_session:
        user = await ChatService.get_user(
            db_session=db_session,
            chat_id=message.chat.id,
            username=message.chat.username,
            fullname=message.chat.full_name
        )
        user.update_config({
            "text_model_id": settings.DEFAULT_TEXT_MODEL_ID,
            "image_model_id": settings.DEFAULT_IMAGE_MODEL_ID,
            "video_model_id": settings.DEFAULT_VIDEO_MODEL_ID
        })
        await user.save(db_session)
        response = Text(START_RESPONSE)
        await message.answer(**response.as_kwargs())
        response = Text(HELP_RESPONSE)
        await message.answer(
            **response.as_kwargs(),
            reply_markup=None
        )


@router.message(Command(commands="help"))
async def process_help_command(message: types.Message):
    response = Text(HELP_RESPONSE)
    await message.answer(**response.as_kwargs())


@router.message(Command(commands="reset"))
async def process_reset_command(
    message: types.Message, db: Database, state: FSMContext
):
    await state.clear()
    response = Text(RESET_RESPONSE)
    async with db.get_session() as db_session:
        await ChatService.get_conv_by_chat_id(
            db_session=db_session,
            chat_id=message.chat.id,
            new=True
        )
    await message.answer(**response.as_kwargs())


@router.message(Command(commands="profile"))
async def process_profile_command(message: types.Message, db: Database):
    async with db.get_session() as db_session:
        user = await ChatService.get_user(
            db_session=db_session,
            chat_id=message.chat.id,
            username=message.chat.username,
            fullname=message.chat.full_name,
        )
        premium_status = "активен ⭐" if user.premium else "не активен"
        response = Text(
            PROFILE_RESPONSE.format(
                balance=user.balance,
                premium_status=premium_status,
            )
        )
        await message.answer(**response.as_kwargs())


@router.message(Command(commands="models"))
async def process_models_command(
    message: types.Message, db: Database, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    ai_menu_id = data.get("ai_menu_id")
    try:
        if ai_menu_id:
            await bot.delete_message(message.chat.id, ai_menu_id)
    except Exception:
        pass

    async with db.get_session() as db_session:
        user = await ChatService.get_user(db_session, message.chat.id)
        user_models = await AIService.get_user_models(
            db_session, user.config
        )
        text_model = user_models.get("text").name \
            if user_models.get("text") else "не выбрана"
        image_model = user_models.get("image").name \
            if user_models.get("image") else "не выбрана"
        video_model = user_models.get("video").name \
            if user_models.get("video") else "не выбрана"
        response = (
            "Текущие модели для генерации:\n"
            f"📃 текст: *{text_model}*\n"
            f"🖼 изображение: *{image_model}*\n"
            f"🎥 видео: *{video_model}*\n\n"
            "Изменить:"
        )
        cats = await AIService.get_categories(db_session)
        ai_menu = await message.answer(
            text=response,
            reply_markup=get_inline_cats_kb(cats)
        )
        await state.update_data(ai_menu_id=ai_menu.message_id)


@router.callback_query(MenuCloseCBF.filter())
async def process_close_menu_callback(
    callback: types.CallbackQuery, state: FSMContext, bot: Bot
):
    await callback.answer()
    data = await state.get_data()
    ai_menu_id = data.get("ai_menu_id")
    try:
        if ai_menu_id:
            await bot.delete_message(callback.message.chat.id, ai_menu_id)
    except Exception:
        pass


@router.callback_query(AIMainCBF.filter())
async def process_main_ai_callback(
    callback: types.CallbackQuery, db: Database, state: FSMContext, bot: Bot
):
    await callback.answer()
    data = await state.get_data()
    ai_menu_id = data.get("ai_menu_id")
    try:
        if ai_menu_id:
            await bot.delete_message(callback.message.chat.id, ai_menu_id)
    except Exception:
        pass

    async with db.get_session() as db_session:
        user = await ChatService.get_user(db_session, callback.message.chat.id)
        user_models = await AIService.get_user_models(
            db_session, user.config
        )
        text_model = user_models.get("text").name \
            if user_models.get("text") else "не выбрана"
        image_model = user_models.get("image").name \
            if user_models.get("image") else "не выбрана"
        video_model = user_models.get("video").name \
            if user_models.get("video") else "не выбрана"
        response = (
            "Текущие модели для генерации:\n"
            f"📃 текст: *{text_model}*\n"
            f"🖼 изображение: *{image_model}*\n"
            f"🎥 видео: *{video_model}*\n\n"
            "Изменить:"
        )
        cats = await AIService.get_categories(db_session)
        ai_menu = await callback.message.answer(
            text=response,
            reply_markup=get_inline_cats_kb(cats)
        )
        await state.update_data(ai_menu_id=ai_menu.message_id)


@router.callback_query(AICategoryCBF.filter())
async def process_category_callback(
    callback: types.CallbackQuery, callback_data: AICategoryCBF, db: Database,
    state: FSMContext, bot: Bot
):
    await callback.answer()
    data = await state.get_data()
    ai_menu_id = data.get("ai_menu_id")
    try:
        if ai_menu_id:
            await bot.delete_message(callback.message.chat.id, ai_menu_id)
    except Exception:
        pass
    async with db.get_session() as db_session:
        user = await ChatService.get_user(db_session, callback.message.chat.id)
        user_models = await AIService.get_user_models(
            db_session, user.config
        )
        category_id = callback_data.cat_id
        cat = cat_list[category_id]
        chosen_model_id = None
        if user_models.get(cat.alias):
            chosen_model_id = user_models.get(cat.alias).id
        response = "Выбери модель:"
        models = await AIService.get_models(db_session, cat.alias)
        ai_menu = await callback.message.answer(
            text=response,
            reply_markup=get_inline_models_kb(
                cat_id=category_id,
                models=models,
                chosen_model_id=chosen_model_id
            )
        )
        await state.update_data(ai_menu_id=ai_menu.message_id)


@router.callback_query(AIModelCBF.filter())
async def process_model_callback(
    callback: types.CallbackQuery, callback_data: AIModelCBF, db: Database,
    state: FSMContext, bot: Bot
):
    await callback.answer("Сохранено")
    data = await state.get_data()
    ai_menu_id = data.get("ai_menu_id")
    try:
        if ai_menu_id:
            await bot.delete_message(callback.message.chat.id, ai_menu_id)
    except Exception:
        pass
    async with db.get_session() as db_session:
        category_id = callback_data.cat_id
        cat = cat_list[category_id]
        chosen_model_id = callback_data.model_id
        user = await ChatService.get_user(db_session, callback.message.chat.id)
        user.update_config({
            f"{cat.alias}_model_id": int(chosen_model_id)
        })
        await user.save(db_session)
        response = "Выбери модель:"
        models = await AIService.get_models(db_session, cat.alias)
        ai_menu = await callback.message.answer(
            text=response,
            reply_markup=get_inline_models_kb(
                cat_id=category_id,
                models=models,
                chosen_model_id=chosen_model_id
            )
        )
        await state.update_data(ai_menu_id=ai_menu.message_id)


@router.message(Command(commands="admin"))
async def process_admin_command(message: types.Message, db: Database):
    async with db.get_session() as db_session:
        user = await ChatService.get_user(db_session, message.chat.id)
        if user.is_admin:
            response = Text(
                "admin"
            )
            await message.answer(
                **response.as_kwargs(),
                reply_markup=None
            )
        else:
            await message.delete()


def split_string_into_chunks(text: str, max_length: int = 2000):
    """
    Split text into chunks of maximum length, preserving word boundaries and \
newlines.

    Args:
        text (str): The input text to split
        max_length (int): Maximum chunk length (default: 2000)

    Returns:
        list: List of text chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    lines = text.split('\n')

    for line in lines:
        if len(line) > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            words = line.split()
            temp_chunk = ""
            for word in words:
                if len(temp_chunk) + len(word) + 1 > max_length:
                    if temp_chunk:
                        chunks.append(temp_chunk)
                    temp_chunk = word
                else:
                    temp_chunk += " " + word if temp_chunk else word
            if temp_chunk:
                chunks.append(temp_chunk)
        elif len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += "\n" + line if current_chunk else line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


async def _run_user_graph(state: GraphState) -> dict[str, Any] | None:
    graph = graph_builder.compile()
    try:
        return await graph.ainvoke(input=state)
    except Exception:
        logger.exception("LangGraph ainvoke failed")
        return None


def _aimessage_to_plain(msg: AIMessage) -> str:
    return message_text(msg.content).replace("###", "").replace("**", "")


def _build_human_turn(
    user_text: str,
    images_b64: list[str],
    *,
    from_video: bool = False,
) -> HumanMessage:
    t = (user_text or "").strip()
    if not images_b64:
        return HumanMessage(content=t or " ")

    if not t:
        if from_video:
            t = (
                "Пользователь прислал видео без подписи. По кадрам видео, "
                "истории диалога определи: нужен текстовый ответ, новая "
                "картинка или видео."
            )
        else:
            t = (
                "Пользователь прислал изображения без подписи. По истории диалога "
                "и картинкам определи: нужен текстовый ответ, новая картинка или видео."
            )

    parts: list[dict] = [{"type": "text", "text": t}]
    for b64 in images_b64[:10]:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )
    return HumanMessage(content=parts)


_video_document = F.document & F.document.mime_type.startswith("video/")


@router.message(
    (F.text & ~F.text.startswith("/"))
    | F.photo
    | F.video
    | _video_document
)
async def process_message(
    message: types.Message,
    db: Database,
    system_llm: ChatOpenAI,
    bot: Bot,
    album_messages: list[types.Message] | None = None,
):
    if (message.text and message.text.startswith("/")) or (
        message.caption and message.caption.startswith("/")
    ):
        return

    try:
        async with db.get_session() as db_session:
            user = await ChatService.get_user(
                db_session=db_session,
                chat_id=message.chat.id,
                username=message.chat.username,
                fullname=message.chat.full_name
            )
            conv = await ChatService.get_conv(
                db_session=db_session,
                user_id=user.id,
            )

            group = album_messages if album_messages else [message]
            group = sorted(group, key=lambda m: m.message_id)
            photo_msgs = [m for m in group if m.photo][:10]
            video_msg = next((m for m in group if message_has_video(m)), None)
            if video_msg is None and message_has_video(message):
                video_msg = message

            user_visible = album_user_text(group)
            if not user_visible:
                user_visible = (message.caption or message.text or "").strip()

            images_b64: list[str] = []
            if photo_msgs:
                images_b64 = await download_album_photos_as_base64(
                    bot, photo_msgs, max_images=10
                )
            from_video = False
            if video_msg and len(images_b64) < 10:
                video_frames = await download_message_video_frames_as_base64(
                    bot, video_msg,
                    max_frames=min(
                        settings.VIDEO_MAX_FRAMES,
                        10 - len(images_b64),
                    ),
                )
                if video_frames:
                    from_video = not photo_msgs
                    images_b64.extend(video_frames)

            if not user_visible and not images_b64:
                await message.answer(
                    "Пришлите текст, фото или видео (можно с подписью)."
                )
                return

            if video_msg and not photo_msgs:
                stored_user = user_visible if user_visible else "[видео]"
            elif images_b64:
                n = len(images_b64)
                if video_msg and photo_msgs:
                    stored_user = user_visible if user_visible else f"[фото+видео, {n} кадров]"
                else:
                    stored_user = user_visible if user_visible else f"[{n} фото]"
            else:
                stored_user = user_visible

            await Message(
                text=stored_user,
                is_bot=False,
                conversation_id=conv.id
            ).save(db_session)

            history = await ChatService.get_last_messages_as_langchain(
                db_session=db_session, conv_id=conv.id, limit=10
            )
            if history and getattr(history[-1], "type", None) == "human":
                history = history[:-1]

            human_turn = _build_human_turn(
                user_visible, images_b64, from_video=from_video
            )
            messages_lc = history + [human_turn]

            models = await AIService.get_user_models(db_session, user.config)
            input_data: GraphState = {
                "balance": user.balance,
                "models": models,
                "messages": messages_lc,
                "system_llm": system_llm,
                "chat_id": message.chat.id,
                "conversation_id": str(conv.id),
            }
            main_task = asyncio.create_task(_run_user_graph(input_data))
            while not main_task.done():
                await message.chat.do("typing")
                try:
                    await asyncio.wait_for(
                        asyncio.shield(main_task), timeout=4.9
                    )
                except asyncio.TimeoutError:
                    continue
            task_result = await main_task
            if not task_result:
                await message.answer("Не удалось обработать запрос. Попробуйте ещё раз.")
                return

            result_msg = task_result.get("result")
            if not isinstance(result_msg, AIMessage):
                await message.answer("Не удалось получить ответ модели.")
                return

            reply_plain = _aimessage_to_plain(result_msg)
            await Message(
                text=reply_plain,
                is_bot=True,
                conversation_id=conv.id
            ).save(db_session)
            price = task_result.get("price")
            if price is not None:
                user.balance -= int(round(float(price)))
                await user.save(db_session)

            photo_url = task_result.get("photo_url")
            photo_bytes = task_result.get("photo_bytes")
            video_bytes = task_result.get("video_bytes")
            cap = (reply_plain[:1024] if reply_plain else None) or None

            if photo_url:
                await message.answer_photo(
                    photo_url, caption=cap, parse_mode=None
                )
            elif photo_bytes:
                await message.answer_photo(
                    BufferedInputFile(photo_bytes, filename="image.png"),
                    caption=cap,
                    parse_mode=None,
                )
            elif video_bytes:
                await message.answer_video(
                    BufferedInputFile(video_bytes, filename="video.mp4"),
                    caption=cap,
                    parse_mode=None,
                )
            else:
                await message.answer(text=reply_plain)
    except Exception as e:
        await message.answer(
            "Произошла ошибка во время обработки запроса."
        )
        logger.exception("process_message failed: %s", e)


@router.message()
async def process_unnecessary_message(message: types.Message):
    await message.delete()
