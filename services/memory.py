import asyncio
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

from core.config import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """MemPalace long-term memory scoped per Telegram user."""

    SOURCE = "yaai-bot"

    @classmethod
    def wing(cls, chat_id: int) -> str:
        return f"user_{chat_id}"

    @classmethod
    def _palace_path(cls) -> str:
        path = Path(settings.MEMPALACE_PALACE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @classmethod
    def _format_results(cls, payload: dict) -> str:
        items = payload.get("results") or []
        if not items:
            return ""
        lines: list[str] = []
        for idx, item in enumerate(items, start=1):
            text = str(item.get("text") or "").strip()
            if text:
                lines.append(f"{idx}. {text}")
        return "\n".join(lines)

    @classmethod
    def _retrieve_sync(cls, chat_id: int, query: str, top_k: int | None) -> str:
        from mempalace.searcher import search_memories

        payload = search_memories(
            query=query,
            palace_path=cls._palace_path(),
            wing=cls.wing(chat_id),
            room=settings.MEMPALACE_ROOM,
            n_results=top_k or settings.MEMPALACE_TOP_K,
        )
        return cls._format_results(payload)

    @classmethod
    async def retrieve(
        cls,
        chat_id: int,
        query: str,
        *,
        top_k: int | None = None,
    ) -> str:
        if not settings.MEMPALACE_ENABLED:
            return ""
        q = (query or "").strip()
        if not q:
            return ""
        try:
            return await asyncio.to_thread(cls._retrieve_sync, chat_id, q, top_k)
        except Exception:
            logger.exception("MemPalace retrieve failed for chat_id=%s", chat_id)
            return ""

    @classmethod
    def _drawer_id(cls, wing: str, room: str, content: str) -> str:
        from mempalace.ids import make_drawer_id_from_content

        return make_drawer_id_from_content(wing, room, content)

    @classmethod
    def _store_sync(
        cls,
        chat_id: int,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        from mempalace.config import sanitize_content, sanitize_name
        from mempalace.ids import ID_RECIPE
        from mempalace.palace import get_collection

        wing = sanitize_name(cls.wing(chat_id), "wing")
        room = sanitize_name(settings.MEMPALACE_ROOM, "room")
        user_part = (user_text or "").strip() or "[без текста]"
        assistant_part = (assistant_text or "").strip()
        if not assistant_part:
            return

        document = sanitize_content(
            f"USER: {user_part}\nASSISTANT: {assistant_part}"
        )
        drawer_id = cls._drawer_id(wing, room, document)
        metadata = {
            "wing": wing,
            "room": room,
            "session_id": conversation_id,
            "chat_id": str(chat_id),
            "source_file": cls.SOURCE,
            "filed_at": datetime.now().isoformat(),
            "ingest_mode": "yaai_bot",
            "id_recipe": ID_RECIPE,
            "chunk_index": 0,
        }

        collection = get_collection(cls._palace_path(), create=True)
        existing = collection.get(ids=[drawer_id], include=[])
        if existing.get("ids"):
            return

        collection.upsert(
            ids=[drawer_id],
            documents=[document],
            metadatas=[metadata],
        )

    @classmethod
    async def store_turn(
        cls,
        chat_id: int,
        conversation_id: str | UUID,
        user_text: str,
        assistant_text: str,
    ) -> None:
        if not settings.MEMPALACE_ENABLED:
            return
        try:
            await asyncio.to_thread(
                cls._store_sync,
                chat_id,
                str(conversation_id),
                user_text,
                assistant_text,
            )
        except Exception:
            logger.exception("MemPalace store failed for chat_id=%s", chat_id)
