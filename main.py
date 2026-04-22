"""Точка входа FastAPI-приложения OpenAI proxy."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from app.client import create_http_client
from app.config import get_settings
from app.logging_setup import configure_logging
from app.routes import create_router, get_client_dep, get_settings_dep
from app.version import __version__


load_dotenv()
settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("app.main")

app = FastAPI(title="openai-proxy", version=__version__)
http_client = create_http_client(settings)

# Подмена зависимостей роутера на реальные объекты приложения.
app.dependency_overrides[get_settings_dep] = lambda: settings
app.dependency_overrides[get_client_dep] = lambda: http_client

app.include_router(create_router())


@app.on_event("startup")
async def on_startup() -> None:
    """Логирует ключевую информацию о запуске сервиса."""

    proxy_active = bool(os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"))
    logger.info("service started version=%s base_url=%s", __version__, settings.openai_base_url)
    logger.info("proxy_env_active=%s", proxy_active)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Корректно закрывает HTTP-клиент при завершении."""

    await http_client.aclose()
    logger.info("service stopped")
