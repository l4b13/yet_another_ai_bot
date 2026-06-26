import asyncio
import base64
import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message

from core.config import settings

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 15 * 1024 * 1024


def album_user_text(messages: list[Message]) -> str:
    """Подпись в альбоме обычно только у одного сообщения; собираем все непустые."""
    parts: list[str] = []
    for m in messages:
        t = (m.caption or m.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def message_has_video(message: Message) -> bool:
    if message.video:
        return True
    doc = message.document
    return bool(doc and doc.mime_type and doc.mime_type.startswith("video/"))


def _video_file_id(message: Message) -> str | None:
    if message.video:
        return message.video.file_id
    doc = message.document
    if doc and doc.mime_type and doc.mime_type.startswith("video/"):
        return doc.file_id
    return None


async def download_largest_photo_bytes(bot: Bot, message: Message) -> bytes | None:
    if not message.photo:
        return None
    photo = message.photo[-1]
    try:
        f = await bot.get_file(photo.file_id)
        if not f.file_path:
            return None
        buf = BytesIO()
        await bot.download_file(f.file_path, buf)
        data = buf.getvalue()
        if len(data) > MAX_PHOTO_BYTES:
            logger.warning("Photo too large (%s bytes), skipping", len(data))
            return None
        return data
    except Exception:
        logger.exception("download_largest_photo_bytes failed")
        return None


async def download_video_bytes(bot: Bot, message: Message) -> bytes | None:
    file_id = _video_file_id(message)
    if not file_id:
        return None
    try:
        f = await bot.get_file(file_id)
        if not f.file_path:
            return None
        buf = BytesIO()
        await bot.download_file(f.file_path, buf)
        data = buf.getvalue()
        if len(data) > settings.VIDEO_MAX_BYTES:
            logger.warning("Video too large (%s bytes), skipping", len(data))
            return None
        return data
    except Exception:
        logger.exception("download_video_bytes failed")
        return None


def extract_video_frames_as_base64(
    video_bytes: bytes,
    *,
    max_frames: int | None = None,
) -> list[str]:
    limit = max_frames or settings.VIDEO_MAX_FRAMES
    if limit <= 0:
        return []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        video_path = tmp_path / "input.bin"
        video_path.write_bytes(video_bytes)
        out_pattern = str(tmp_path / "frame_%03d.jpg")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            "fps=1,scale='min(768,iw)':-1",
            "-frames:v",
            str(limit),
            "-q:v",
            "3",
            out_pattern,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,
                check=False,
            )
            if proc.returncode != 0:
                logger.warning(
                    "ffmpeg failed: %s",
                    proc.stderr.decode(errors="replace")[-500:],
                )
                return []
        except FileNotFoundError:
            logger.warning("ffmpeg not found; video frames skipped")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timed out")
            return []

        out: list[str] = []
        for frame in sorted(tmp_path.glob("frame_*.jpg"))[:limit]:
            out.append(base64.standard_b64encode(frame.read_bytes()).decode("ascii"))
        return out


async def download_message_video_frames_as_base64(
    bot: Bot,
    message: Message,
    *,
    max_frames: int | None = None,
) -> list[str]:
    raw = await download_video_bytes(bot, message)
    if not raw:
        return []
    return await asyncio.to_thread(
        extract_video_frames_as_base64,
        raw,
        max_frames=max_frames,
    )


async def download_album_photos_as_base64(
    bot: Bot,
    messages: list[Message],
    *,
    max_images: int = 10,
) -> list[str]:
    out: list[str] = []
    for m in messages:
        if len(out) >= max_images:
            break
        if not m.photo:
            continue
        raw = await download_largest_photo_bytes(bot, m)
        if raw:
            out.append(base64.standard_b64encode(raw).decode("ascii"))
    return out
