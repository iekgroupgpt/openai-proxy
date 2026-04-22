"""Логика симметричного проксирования запросов в OpenAI API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable

import httpx
from fastapi import HTTPException, Request, Response

from app.config import Settings

logger = logging.getLogger("app.proxy")

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _filtered_request_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Удаляет hop-by-hop заголовки, остальное проксирует 1:1."""

    prepared: dict[str, str] = {}
    for key, value in headers:
        key_lower = key.lower()
        if key_lower in _HOP_BY_HOP_HEADERS:
            continue
        if key_lower == "host":
            continue
        prepared[key] = value
    return prepared


def _filtered_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Удаляет hop-by-hop заголовки из ответа upstream."""

    prepared: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _HOP_BY_HOP_HEADERS:
            continue
        prepared[key] = value
    return prepared


async def proxy_request(
    request: Request,
    settings: Settings,
    client: httpx.AsyncClient,
    upstream_path: str,
) -> Response:
    """Проксирует входящий запрос в OpenAI и возвращает ответ без преобразований."""

    upstream_url = f"{settings.openai_base_url}/{upstream_path.lstrip('/')}"
    method = request.method.upper()
    params = request.query_params
    headers = _filtered_request_headers(request.headers.items())
    body = await request.body()

    # Небольшой, но надежный retry для сетевых ошибок и временных статусов.
    retryable_statuses = {429, 500, 502, 503, 504}

    started_at = time.perf_counter()

    for attempt in range(settings.max_retries + 1):
        try:
            upstream_response = await client.request(
                method=method,
                url=upstream_url,
                params=params,
                headers=headers,
                content=body,
            )

            if upstream_response.status_code in retryable_statuses and attempt < settings.max_retries:
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue

            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "proxied method=%s path=/%s status=%s latency_ms=%s",
                method,
                upstream_path.lstrip("/"),
                upstream_response.status_code,
                elapsed_ms,
            )

            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                headers=_filtered_response_headers(upstream_response.headers),
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            if attempt < settings.max_retries:
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue
            logger.warning("upstream timeout method=%s path=/%s error=%s", method, upstream_path, exc)
            raise HTTPException(status_code=504, detail="Upstream timeout") from exc
        except httpx.RequestError as exc:
            if attempt < settings.max_retries:
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue
            logger.error("upstream request error method=%s path=/%s error=%s", method, upstream_path, exc)
            raise HTTPException(status_code=502, detail="Upstream request error") from exc

    # Теоретически недостижимая ветка, добавлена для явности.
    raise HTTPException(status_code=502, detail="Proxy error")
