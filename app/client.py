"""Создание и управление HTTP-клиентом для обращений к OpenAI."""

from __future__ import annotations

import httpx

from app.config import Settings


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """Создает общий AsyncClient c таймаутами и учетом proxy-переменных окружения."""

    timeout = httpx.Timeout(
        connect=settings.request_timeout_connect,
        read=settings.request_timeout_read,
        write=settings.request_timeout_write,
        pool=settings.request_timeout_pool,
    )

    # trust_env=True нужен, чтобы httpx использовал HTTP_PROXY/HTTPS_PROXY/NO_PROXY.
    return httpx.AsyncClient(timeout=timeout, trust_env=True, follow_redirects=False)
