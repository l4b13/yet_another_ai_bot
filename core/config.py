from pydantic import PostgresDsn, RedisDsn, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".dev.env"),
        env_ignore_empty=True,
        extra="ignore",
        env_file_encoding='utf-8',
    )

    PROJECT_NAME: str

    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str
    LOG_FILE: str = "./data/logs/info.log"

    BOT_TOKEN: str

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_DB: int

    OPENAI_BASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_IMAGES_PATH: str = "/images/generations"
    OPENAI_VIDEOS_PATH: str = "/videos"
    OPENAI_IMAGE_SIZE: str = "1024x1024"
    OPENAI_VIDEO_SIZE: str = "1280x720"
    OPENAI_VIDEO_SECONDS: str = "5"
    OPENAI_VIDEO_POLL_INTERVAL: float = 10.0

    MEDIA_GROUP_DEBOUNCE_SEC: float = 0.85
    VIDEO_MAX_BYTES: int = 20 * 1024 * 1024
    VIDEO_MAX_FRAMES: int = 5

    MEMPALACE_ENABLED: bool = True
    MEMPALACE_PALACE_PATH: str = "./data/mempalace/palace"
    MEMPALACE_ROOM: str = "telegram"
    MEMPALACE_TOP_K: int = 5

    DEFAULT_TEXT_MODEL_ID: int
    DEFAULT_IMAGE_MODEL_ID: int
    DEFAULT_VIDEO_MODEL_ID: int

    @computed_field
    @property
    def redis_url(self) -> RedisDsn:
        return MultiHostUrl.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            password=self.REDIS_PASSWORD
        )

    @computed_field
    @property
    def asyncpg_url(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @computed_field
    @property
    def postgres_url(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )


def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()

__all__ = ['settings']
