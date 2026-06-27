import base64
import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def _api_base() -> str:
    return settings.OPENAI_BASE_URL.rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


def _first_media_item(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        return data[0]
    return None


async def request_image(
    prompt: str,
    model: str,
    *,
    timeout: float = 180.0,
) -> tuple[bytes | None, str | None, str | None]:
    """Returns (image_bytes, image_url, error)."""
    path = settings.OPENAI_IMAGES_PATH.lstrip("/")
    url = f"{_api_base()}/{path}"
    base_body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
    }
    if settings.OPENAI_IMAGE_SIZE:
        base_body["size"] = settings.OPENAI_IMAGE_SIZE

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(url, json=base_body, headers=_headers())
        except httpx.RequestError as e:
            return None, None, f"Сеть: {e!s}"

        if r.status_code >= 400:
            err_text = r.text
            try:
                err_text = str(r.json())
            except Exception:
                pass
            return None, None, f"HTTP {r.status_code}: {err_text}"

        try:
            payload = r.json()
        except Exception:
            return None, None, "Некорректный JSON от API изображений"

        item = _first_media_item(payload)
        if not item and isinstance(payload.get("data"), dict):
            item = payload["data"]

        if not item:
            return None, None, "Пустой ответ API изображений"

        if u := item.get("url"):
            return None, str(u), None
        if b64 := item.get("b64_json"):
            try:
                return base64.b64decode(b64), None, None
            except Exception:
                return None, None, "Не удалось декодировать b64_json"

        return None, None, "API изображений не вернул ни url, ни b64_json"


async def request_video(
    prompt: str,
    model: str,
    *,
    timeout: float = 600.0,
) -> tuple[str | None, str | None]:
    """Returns (video_url, error). Provider must expose OpenAI-style HTTP."""
    path = settings.OPENAI_VIDEOS_PATH.lstrip("/")
    url = f"{_api_base()}/{path}"
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(url, json=body, headers=_headers())
        except httpx.RequestError as e:
            return None, f"Сеть: {e!s}"

        if r.status_code >= 400:
            err_text = r.text
            try:
                err_text = str(r.json())
            except Exception:
                pass
            return None, f"HTTP {r.status_code}: {err_text}"

        try:
            payload = r.json()
        except Exception:
            return None, "Некорректный JSON от API видео"

        if vu := payload.get("url"):
            return str(vu), None

        item = _first_media_item(payload)
        if item:
            if vu := item.get("url"):
                return str(vu), None
            if vu := item.get("video_url"):
                return str(vu), None

        return None, (
            "Видео не получено: провайдер не вернул url (путь "
            f"{settings.OPENAI_VIDEOS_PATH} может отличаться у вашего API)."
        )
