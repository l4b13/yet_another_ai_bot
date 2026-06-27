import asyncio
import base64
import logging
import time
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def _api_base() -> str:
    return settings.OPENAI_BASE_URL.rstrip("/")


def _auth_headers(*, json_body: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _first_media_item(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        return data[0]
    return None


def _format_api_error(response: httpx.Response) -> str:
    err_text = response.text
    try:
        err_text = str(response.json())
    except Exception:
        pass
    return f"HTTP {response.status_code}: {err_text}"


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
            r = await client.post(url, json=base_body, headers=_auth_headers(json_body=True))
        except httpx.RequestError as e:
            return None, None, f"Сеть: {e!s}"

        if r.status_code >= 400:
            return None, None, _format_api_error(r)

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


async def _create_sora_video_job(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    model: str,
    reference_image: bytes | None = None,
) -> tuple[str | None, str | None]:
    url = f"{_api_base()}/{settings.OPENAI_VIDEOS_PATH.lstrip('/')}"
    fields = {
        "prompt": prompt,
        "model": model,
        "size": settings.OPENAI_VIDEO_SIZE,
        "seconds": str(settings.OPENAI_VIDEO_SECONDS),
    }

    try:
        if reference_image:
            r = await client.post(
                url,
                headers=_auth_headers(),
                data=fields,
                files={
                    "input_reference": ("reference.jpg", reference_image, "image/jpeg"),
                },
            )
        else:
            r = await client.post(
                url,
                json=fields,
                headers=_auth_headers(json_body=True),
            )
    except httpx.RequestError as e:
        return None, f"Сеть: {e!s}"

    if r.status_code >= 400:
        return None, _format_api_error(r)

    try:
        payload = r.json()
    except Exception:
        return None, "Некорректный JSON при создании видео-задания"

    video_id = payload.get("id")
    if not video_id:
        return None, "API видео не вернул id задания"

    return str(video_id), None


async def _wait_sora_video_job(
    client: httpx.AsyncClient,
    video_id: str,
    *,
    timeout: float,
) -> str | None:
    url = f"{_api_base()}/videos/{video_id}"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            r = await client.get(url, headers=_auth_headers())
        except httpx.RequestError as e:
            return f"Сеть: {e!s}"

        if r.status_code >= 400:
            return _format_api_error(r)

        try:
            payload = r.json()
        except Exception:
            return "Некорректный JSON при проверке статуса видео"

        status = payload.get("status")
        progress = payload.get("progress")
        logger.info(
            "Sora video %s status=%s progress=%s",
            video_id,
            status,
            progress,
        )

        if status == "completed":
            return None
        if status == "failed":
            err = payload.get("error") or payload
            return f"Генерация видео не удалась: {err}"

        await asyncio.sleep(settings.OPENAI_VIDEO_POLL_INTERVAL)

    return "Превышено время ожидания генерации видео"


async def _download_sora_video(
    client: httpx.AsyncClient,
    video_id: str,
) -> tuple[bytes | None, str | None]:
    url = f"{_api_base()}/videos/{video_id}/content"
    try:
        r = await client.get(url, headers=_auth_headers(), follow_redirects=True)
    except httpx.RequestError as e:
        return None, f"Сеть: {e!s}"

    if r.status_code >= 400:
        return None, _format_api_error(r)

    if not r.content:
        return None, "Пустой ответ при скачивании видео"

    return r.content, None


async def request_video(
    prompt: str,
    model: str,
    *,
    reference_image: bytes | None = None,
    timeout: float = 600.0,
) -> tuple[bytes | None, str | None]:
    """Returns (video_bytes, error). Uses Sora async API via ProxyAPI."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        video_id, err = await _create_sora_video_job(
            client,
            prompt=prompt,
            model=model,
            reference_image=reference_image,
        )
        if err:
            return None, err

        err = await _wait_sora_video_job(client, video_id, timeout=timeout)
        if err:
            return None, err

        return await _download_sora_video(client, video_id)
