# openai-proxy

Простой и надежный FastAPI-прокси для OpenAI API.

## Что делает

- Симметрично проксирует основные endpoint'ы:
  - `POST /v1/chat/completions`
  - `POST /v1/embeddings`
  - `POST /v1/responses`
  - `GET /v1/models`
- Поддерживает fallback на любые `v1` маршруты: `ANY /v1/{path:path}`.
- Использует стандартные переменные `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` для исходящих запросов.
- Возвращает клиенту статус, заголовки и тело ответа OpenAI без изменений.
- Поддерживает прозрачный streaming passthrough: если запрос/ответ потоковый, прокси отдает чанки клиенту в реальном времени.
- Имеет простое логирование с ротацией файла 10MB.

## Быстрый старт

1. Скопируйте env-файл:

```bash
cp .env.example .env
```

2. Укажите в `.env` `HTTP_PROXY`/`HTTPS_PROXY` при необходимости.

3. Запуск через Docker Compose:

```bash
docker compose up --build -d
```

4. Проверка:

```bash
curl http://localhost:8000/healthz
```

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Пример запроса

```bash
curl -X POST http://localhost:8000/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4.1-mini","input":"Привет"}'
```

## Примечания по надежности

- Таймауты и retries настраиваются через `.env`.
- По умолчанию `MAX_RETRIES=0`, чтобы запросы не "зависали" из-за повторов; при необходимости ретраи можно включить через `.env`.
- Если ретраи включены, они применяются только для идемпотентных методов (GET/HEAD/OPTIONS), чтобы не дублировать POST-запросы.
- Прокси не подставляет свой API-ключ и не навязывает авторизацию.
- Для снижения риска утечек в логах не пишутся чувствительные заголовки и тело запросов.


## Версия

Текущая версия: `0.1.5`.


## Пример streaming-запроса

```bash
curl -N -X POST http://localhost:8000/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4.1-mini","stream":true,"input":"Расскажи шутку"}'
```
