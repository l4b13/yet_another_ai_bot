# yaai-bot

Telegram-бот с текстовыми ответами, генерацией изображений и видео, поддержкой фото/видео с промптом и долговременной памятью (MemPalace).

## Локальный запуск

```bash
pip install uv
uv sync
cp .example.env .env   # заполните переменные
uv run main.py
```

Нужны PostgreSQL, Redis и заполненная таблица `aimodels` (см. раздел «База данных»).

---

## Деплой на сервере (Docker)

### 1. Требования

- Linux-сервер (VPS)
- Docker Engine 24+ и Docker Compose v2
- Открытый исходящий HTTPS (бот ходит в Telegram и OpenAI-compatible API)
- ~2 GB RAM (MemPalace при первом запросе скачивает embedding-модель ~80 MB)

### 2. Подготовка сервера

```bash
# Ubuntu/Debian — установка Docker (если ещё нет)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# перелогиньтесь, чтобы группа docker применилась

git clone <url-репозитория> yaai-bot
cd yaai-bot
```

Создайте внешнюю сеть (один раз на сервере):

```bash
docker network create shared-network
```

### 3. Конфигурация `.env`

Скопируйте шаблон и заполните:

```bash
cp .example.env .env
nano .env
```

Обязательные переменные:

| Переменная | Пример | Описание |
|------------|--------|----------|
| `PROJECT_NAME` | `yaai` | Имя проекта |
| `BOT_TOKEN` | | Токен от @BotFather |
| `LOG_LEVEL` | `INFO` | Уровень логов |
| `LOG_FORMAT` | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | Формат логов |
| `POSTGRES_USER` | `postgres` | |
| `POSTGRES_PASSWORD` | | Надёжный пароль |
| `POSTGRES_DB` | `yaai` | |
| `POSTGRES_HOST` | `localhost` | Для compose переопределяется на `db` |
| `POSTGRES_PORT` | `5432` | На хосте проброшен `6024` |
| `REDIS_PASSWORD` | | Пароль Redis |
| `REDIS_HOST` | `localhost` | Для compose → `redis` |
| `REDIS_PORT` | `6379` | |
| `REDIS_DB` | `0` | |
| `OPENAI_BASE_URL` | `https://api.proxyapi.ru/openai/v1` | OpenAI-compatible API |
| `OPENAI_API_KEY` | | Ключ API |
| `DEFAULT_TEXT_MODEL_ID` | `2` | ID из таблицы `aimodels` |
| `DEFAULT_IMAGE_MODEL_ID` | `6` | |
| `DEFAULT_VIDEO_MODEL_ID` | `11` | |
| `PYTHONUNBUFFERED` | `1` | |

Опционально:

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MEMPALACE_ENABLED` | `true` | Долговременная память |
| `MEMPALACE_PALACE_PATH` | `/app/data/mempalace/palace` | В compose задаётся автоматически |
| `VIDEO_MAX_FRAMES` | `5` | Кадров из входящего видео для vision |
| `MEDIA_GROUP_DEBOUNCE_SEC` | `0.85` | Задержка сборки альбомов фото |

### 4. База данных

При первом запуске бот создаёт таблицы (`create_all`). Заполните справочник моделей и баланс пользователей:

```bash
docker compose up -d db redis
# дождитесь healthcheck Postgres, затем:
docker compose exec db psql -U postgres -d yaai
```

```sql
-- пример: добавьте модели с id, совпадающими с DEFAULT_*_MODEL_ID в .env
INSERT INTO aimodels (id, name, price, premium, aicategory) VALUES
  (2,  'gpt-4o-mini', 1, false, 'text'),
  (6,  'gpt-image-2',   5, false, 'image'),
  (11, 'sora-2',       10, false, 'video')
ON CONFLICT (id) DO NOTHING;

-- стартовый баланс (пример)
UPDATE users SET balance = 100 WHERE balance = 0;
```

Без записей в `aimodels` и при `balance = 0` бот ответит «модель не выбрана» или «не хватает средств».

### 5. Запуск

```bash
docker compose up -d --build
```

Сервисы:

| Сервис | Назначение |
|--------|------------|
| `bot` | Telegram-бот |
| `db` | PostgreSQL + pgvector (порт хоста `6024`) |
| `redis` | FSM / сессии (порт `6379`) |

Volumes:

- `mempalace_data` — долговременная память (ChromaDB)
- `chroma_cache` — кэш embedding-модели
- `postgres_data`, `redis_data` — данные БД

### 6. Проверка

```bash
docker compose ps
docker compose logs -f bot
```

В Telegram: `/start` → текстовый вопрос, фото с подписью, видео с подписью.

### 7. Обновление

```bash
git pull
docker compose up -d --build
```

### 8. Остановка

```bash
docker compose down
# с удалением volumes (ОСТОРОЖНО — потеря БД и памяти):
# docker compose down -v
```

---

## Возможности бота

- **Текст** — вопросы и диалог
- **Фото** — до 10 в альбоме, с подписью или без (vision)
- **Видео** — файл или документ `video/*` с подписью; из видео извлекаются кадры (ffmpeg) для vision и генерации
- **Генерация** — текст / изображение / видео (intent через LangGraph)
- **Команды** — `/start`, `/help`, `/models`, `/reset`

---

## Локальная разработка без Docker

```bash
uv sync
# PostgreSQL и Redis локально, в .env:
# POSTGRES_HOST=localhost, REDIS_HOST=localhost
uv run main.py
```

Для извлечения кадров из видео локально нужен **ffmpeg** в PATH.

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `network shared-network not found` | `docker network create shared-network` |
| «Не хватает средств» | Пополните `users.balance` в БД |
| «Модель не выбрана» | Проверьте `aimodels` и `DEFAULT_*_MODEL_ID` |
| Видео без реакции на картинку | Проверьте `ffmpeg` в контейнере: `docker compose exec bot ffmpeg -version` |
| Долгий первый ответ | MemPalace качает embedding-модель; или `MEMPALACE_ENABLED=false` |
| Ошибка генерации видео | Модель `sora-2` / `sora-2-pro`, endpoint `/videos` (см. [документацию Sora](https://proxyapi.ru/docs/openai-video-sora)) |
