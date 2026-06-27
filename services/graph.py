import base64
import json
import logging
import re
from typing_extensions import TypedDict

from langchain_core.messages import (
    AnyMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy
from langchain_openai import ChatOpenAI

from core.config import settings
from models.aimodel import AIModel
from services.memory import MemoryService
from services.openai_media import request_image, request_video
from static.prompts import (
    CLASSIFY_INSTRUCTION,
    CLASSIFY_JSON_TEMPLATE,
    CLASSIFY_PROMPT,
    IMAGE_EXPAND_CONTEXT_PROMPT,
    MEMORY_CONTEXT_PROMPT,
    SYSTEM_PROMPT,
    VIDEO_EXPAND_CONTEXT_PROMPT,
    VISION_EXPAND_IMAGE_PROMPT,
    VISION_EXPAND_VIDEO_PROMPT,
)

logger = logging.getLogger(__name__)


def message_text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else ""
    return str(content)


def extract_text_and_ref_b64_from_last_human(
    messages: list[AnyMessage],
) -> tuple[str, list[str]]:
    """Текст и base64 из последнего human-сообщения (мультимодальный контент)."""
    if not messages:
        return "", []
    last = messages[-1]
    if getattr(last, "type", None) != "human":
        return message_text(getattr(last, "content", "")), []

    c = last.content
    if isinstance(c, str):
        return c.strip(), []

    if not isinstance(c, list):
        return str(c).strip(), []

    texts: list[str] = []
    b64s: list[str] = []
    for block in c:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            texts.append(str(block["text"]))
        elif block.get("type") == "image_url":
            url_obj = block.get("image_url")
            u = ""
            if isinstance(url_obj, dict):
                u = str(url_obj.get("url", ""))
            elif isinstance(url_obj, str):
                u = url_obj
            if "base64," in u:
                b64s.append(u.split("base64,", 1)[1].strip())

    return "\n".join(texts).strip(), b64s


def md_json_to_dict(llm_output: str) -> dict | list | None:
    text = (llm_output or "").strip()
    json_block = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    candidates: list[str] = []
    if json_block:
        candidates.append(json_block.group(1).strip())

    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break

    for raw in candidates:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


class GraphState(TypedDict, total=False):
    messages: list[AnyMessage]
    balance: int
    price: float
    system_llm: ChatOpenAI
    models: dict[str, AIModel | None]
    result: AIMessage
    photo_url: str
    photo_bytes: bytes
    video_url: str
    video_bytes: bytes
    chat_id: int
    conversation_id: str
    memory_context: str
    route: str
    media_caption: str


def _media_history_text(kind: str, prompt: str) -> str:
    label = "изображение" if kind == "image" else "видео"
    return f"[сгенерировано {label}] {prompt.strip()}"


def _media_caption(user_text: str, prompt: str, fallback: str) -> str:
    src = (user_text or "").strip() or prompt.strip() or fallback
    return (src[:900] + "…") if len(src) > 900 else src


def _memory_system_messages(state: GraphState) -> list[SystemMessage]:
    ctx = (state.get("memory_context") or "").strip()
    if not ctx:
        return []
    return [SystemMessage(content=MEMORY_CONTEXT_PROMPT.format(context=ctx))]


async def retrieve_memory(state: GraphState) -> GraphState:
    logger.info("---RETRIEVE MEMORY---")
    if not settings.MEMPALACE_ENABLED:
        return {"memory_context": ""}

    chat_id = state.get("chat_id")
    if chat_id is None:
        return {"memory_context": ""}

    user_text, _ = extract_text_and_ref_b64_from_last_human(
        state.get("messages") or []
    )
    memory_context = await MemoryService.retrieve(chat_id, user_text)
    if memory_context:
        logger.info(
            "MemPalace retrieved %s chars for chat_id=%s",
            len(memory_context),
            chat_id,
        )
    return {"memory_context": memory_context}


async def store_memory(state: GraphState) -> GraphState:
    logger.info("---STORE MEMORY---")
    if not settings.MEMPALACE_ENABLED:
        return {}

    chat_id = state.get("chat_id")
    conversation_id = state.get("conversation_id")
    result = state.get("result")
    if chat_id is None or not conversation_id or not isinstance(result, AIMessage):
        return {}

    user_text, _ = extract_text_and_ref_b64_from_last_human(
        state.get("messages") or []
    )
    assistant_text = message_text(result.content)
    await MemoryService.store_turn(
        chat_id=chat_id,
        conversation_id=conversation_id,
        user_text=user_text,
        assistant_text=assistant_text,
    )
    return {}


async def _enrich_prompt_for_image(
    llm: ChatOpenAI, user_prompt: str, b64s: list[str]
) -> str:
    body = VISION_EXPAND_IMAGE_PROMPT.format(
        user_prompt=user_prompt or "создай изображение по референсам"
    )
    parts: list[dict] = [{"type": "text", "text": body}]
    for b in b64s[:10]:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b}"},
            }
        )
    try:
        out = await llm.ainvoke([HumanMessage(content=parts)])
        return message_text(out.content).strip() or user_prompt
    except Exception:
        logger.exception("vision enrich image failed")
        return user_prompt or "image from references"


async def _enrich_prompt_for_video(
    llm: ChatOpenAI, user_prompt: str, b64s: list[str]
) -> str:
    body = VISION_EXPAND_VIDEO_PROMPT.format(
        user_prompt=user_prompt or "создай видео по референсам"
    )
    parts: list[dict] = [{"type": "text", "text": body}]
    for b in b64s[:10]:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b}"},
            }
        )
    try:
        out = await llm.ainvoke([HumanMessage(content=parts)])
        return message_text(out.content).strip() or user_prompt
    except Exception:
        logger.exception("vision enrich video failed")
        return user_prompt or "video from references"


async def _expand_media_prompt_from_context(
    llm: ChatOpenAI,
    messages: list[AnyMessage],
    user_prompt: str,
    state: GraphState,
    *,
    instruction: str,
) -> str:
    try:
        out = await llm.ainvoke(
            _memory_system_messages(state)
            + [SystemMessage(content=instruction)]
            + messages[:-1]
            + [HumanMessage(content=user_prompt or " ")]
        )
        expanded = message_text(out.content).strip()
        return expanded or user_prompt
    except Exception:
        logger.exception("media prompt expand from context failed")
        return user_prompt


async def classify(state: GraphState):
    logger.info("---CLASSIFY---")
    messages = state["messages"]
    system_llm = state["system_llm"]
    user_text, refs = extract_text_and_ref_b64_from_last_human(messages)

    question = user_text
    if not question and refs:
        question = (
            f"[Пользователь прислал {len(refs)} изображений без текста. "
            "По истории чата и картинкам определи, нужен текст (1), "
            "картинка (2) или видео (3).]"
        )
    elif not question:
        question = "[Пустой запрос]"

    classify_body = CLASSIFY_PROMPT.format(
        question=question,
        json_template=CLASSIFY_JSON_TEMPLATE,
    )

    if refs:
        classify_content: str | list = [
            {"type": "text", "text": classify_body},
            *[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b}"},
                }
                for b in refs[:10]
            ],
        ]
        classify_human = HumanMessage(content=classify_content)
    else:
        classify_human = HumanMessage(content=classify_body)

    classify_response = await system_llm.ainvoke(
        _memory_system_messages(state)
        + [SystemMessage(content=CLASSIFY_INSTRUCTION)]
        + messages[:-1]
        + [classify_human]
    )

    content = classify_response.content
    body = md_json_to_dict(content if isinstance(content, str) else str(content))

    if isinstance(body, dict):
        raw = body.get("category_id")
        try:
            category_id = int(raw) if raw is not None else 1
        except (TypeError, ValueError):
            category_id = 1
        if category_id == 2:
            return {"route": "generate_image"}
        if category_id == 3:
            return {"route": "generate_video"}
    return {"route": "generate_text"}


def route_after_classify(state: GraphState) -> str:
    return state.get("route") or "generate_text"


async def generate_text(state: GraphState):
    logger.info("---GENERATE TEXT---")
    text_model = state["models"].get("text")
    messages = state["messages"]
    balance = state["balance"]

    if not text_model:
        return {
            "result": AIMessage(
                content="Модель для текста не выбрана. Откройте /models."
            )
        }

    if balance < text_model.price:
        return {
            "result": AIMessage(content="Не хватает средств. Пополните баланс.")
        }

    llm = ChatOpenAI(
        model=text_model.name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    response = await llm.ainvoke(
        _memory_system_messages(state)
        + [SystemMessage(content=SYSTEM_PROMPT)]
        + messages[:-1]
        + [messages[-1]]
    )

    return {"result": response, "price": float(text_model.price)}


async def generate_image(state: GraphState):
    logger.info("---GENERATE IMAGE---")
    messages = state["messages"]
    image_model = state["models"].get("image")
    balance = state["balance"]
    system_llm = state["system_llm"]

    if not image_model:
        return {
            "result": AIMessage(
                content="Модель для изображений не выбрана. Откройте /models."
            )
        }

    if balance < image_model.price:
        return {
            "result": AIMessage(content="Не хватает средств. Пополните баланс.")
        }

    user_text, refs = extract_text_and_ref_b64_from_last_human(messages)
    if refs:
        prompt = await _enrich_prompt_for_image(system_llm, user_text, refs)
    elif len(messages) > 1:
        prompt = await _expand_media_prompt_from_context(
            system_llm,
            messages,
            user_text,
            state,
            instruction=IMAGE_EXPAND_CONTEXT_PROMPT,
        )
    else:
        prompt = user_text

    if not prompt.strip():
        return {
            "result": AIMessage(
                content="Напишите, какое изображение нужно, или пришлите референс."
            )
        }

    img_bytes, img_url, err = await request_image(prompt, image_model.name)
    logger.info("Image generation prompt (%s chars): %s", len(prompt), prompt[:300])

    if err:
        return {"result": AIMessage(content=f"Не удалось создать изображение: {err}")}

    out: GraphState = {
        "result": AIMessage(content=_media_history_text("image", prompt)),
        "media_caption": _media_caption(user_text, prompt, "Изображение готово."),
        "price": float(image_model.price),
    }
    if img_url:
        out["photo_url"] = img_url
    elif img_bytes:
        out["photo_bytes"] = img_bytes
    return out


async def generate_video(state: GraphState):
    logger.info("---GENERATE VIDEO---")
    video_model = state["models"].get("video")
    messages = state["messages"]
    balance = state["balance"]
    system_llm = state["system_llm"]

    if not video_model:
        return {
            "result": AIMessage(
                content="Модель для видео не выбрана. Откройте /models."
            )
        }

    if balance < video_model.price:
        return {
            "result": AIMessage(content="Не хватает средств. Пополните баланс.")
        }

    user_text, refs = extract_text_and_ref_b64_from_last_human(messages)
    if refs:
        prompt = await _enrich_prompt_for_video(system_llm, user_text, refs)
    elif len(messages) > 1:
        prompt = await _expand_media_prompt_from_context(
            system_llm,
            messages,
            user_text,
            state,
            instruction=VIDEO_EXPAND_CONTEXT_PROMPT,
        )
    else:
        prompt = user_text

    if not prompt.strip():
        return {
            "result": AIMessage(
                content="Напишите, какое видео нужно, или пришлите референс-кадры."
            )
        }

    reference_image: bytes | None = None
    if refs:
        try:
            reference_image = base64.b64decode(refs[0])
        except Exception:
            logger.exception("failed to decode video reference image")

    video_bytes, err = await request_video(
        prompt,
        video_model.name,
        reference_image=reference_image,
    )
    logger.info("Video generation prompt (%s chars): %s", len(prompt), prompt[:300])

    if err:
        return {"result": AIMessage(content=f"Не удалось создать видео: {err}")}

    return {
        "result": AIMessage(content=_media_history_text("video", prompt)),
        "media_caption": _media_caption(user_text, prompt, "Видео готово."),
        "video_bytes": video_bytes,
        "price": float(video_model.price),
    }


graph_builder = StateGraph(GraphState)

graph_builder.add_node("retrieve_memory", retrieve_memory, retry_policy=RetryPolicy())
graph_builder.add_node("classify", classify, retry_policy=RetryPolicy())
graph_builder.add_node(
    "generate_text",
    generate_text,
    retry_policy=RetryPolicy(),
)
graph_builder.add_node(
    "generate_image",
    generate_image,
    retry_policy=RetryPolicy(),
)
graph_builder.add_node(
    "generate_video",
    generate_video,
    retry_policy=RetryPolicy(),
)
graph_builder.add_node("store_memory", store_memory, retry_policy=RetryPolicy())

graph_builder.set_entry_point("retrieve_memory")
graph_builder.add_edge("retrieve_memory", "classify")
graph_builder.add_conditional_edges(
    "classify",
    route_after_classify,
    {
        "generate_text": "generate_text",
        "generate_image": "generate_image",
        "generate_video": "generate_video",
    },
)
graph_builder.add_edge("generate_text", "store_memory")
graph_builder.add_edge("generate_image", "store_memory")
graph_builder.add_edge("generate_video", "store_memory")
