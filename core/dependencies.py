from urllib.parse import quote_plus

from celery import Celery

from .config import settings


celery = None


def _redis_broker_url() -> str:
    host = settings.REDIS_HOST
    port = settings.REDIS_PORT
    db = settings.REDIS_DB
    if settings.REDIS_PASSWORD:
        pw = quote_plus(settings.REDIS_PASSWORD)
        return f"redis://:{pw}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_task_manager():
    global celery
    if not celery:
        celery = Celery(
            "YAAI-BOT",
            broker=_redis_broker_url(),
        )
    return celery
