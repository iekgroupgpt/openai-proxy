"""Логика симметричного проксирования запросов в OpenAI API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Iterable

import httpx
from fastapi import HTTPException, Request, Response
from starlette.responses import StreamingResponse

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

_IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS"}


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


def _request_wants_stream(headers: dict[str, str], body: bytes) -> bool:
    """Пытается определить streaming-запрос по JSON полю stream=true."""

    content_type = headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return False

    if not body:
        return False

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return False

    if isinstance(payload, dict):
        return bool(payload.get("stream") is True)
    return False


def _response_is_streaming(headers: httpx.Headers) -> bool:
    """Определяет streaming-ответ по content-type."""

    content_type = headers.get("content-type", "")
    return "text/event-stream" in content_type.lower()


def _build_stream_generator(
    upstream_response: httpx.Response,
    method: str,
    upstream_path: str,
    started_at: float,
) -> AsyncIterator[bytes]:
    """Создает генератор чанков и гарантирует закрытие upstream соединения."""

    async def _iterator() -> AsyncIterator[bytes]:
        bytes_sent = 0
        try:
            async for chunk in upstream_response.aiter_raw():
                bytes_sent += len(chunk)
                yield chunk
        except Exception as exc:
            logger.warning(
                "stream interrupted method=%s path=/%s type=%s error=%r",
                method,
                upstream_path.lstrip("/"),
                type(exc).__name__,
                exc,
            )
            raise
        finally:
            await upstream_response.aclose()
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "stream finished method=%s path=/%s status=%s bytes=%s latency_ms=%s",
                method,
                upstream_path.lstrip("/"),
                upstream_response.status_code,
                bytes_sent,
                elapsed_ms,
            )

    return _iterator()


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

    request_stream_mode = _request_wants_stream(headers, body)

    # Повторяем только идемпотентные запросы (например GET /v1/models),
    # чтобы исключить риск дублей на POST-эндпоинтах генерации.
    retryable_statuses = {429, 500, 502, 503, 504}
    retries_allowed = (
        not request_stream_mode
        and (not settings.retry_idempotent_only or method in _IDEMPOTENT_METHODS)
    )

    started_at = time.perf_counter()
    logger.info(
        "forwarding method=%s path=/%s stream_request=%s retries_allowed=%s max_retries=%s",
        method,
        upstream_path.lstrip("/"),
        request_stream_mode,
        retries_allowed,
        settings.max_retries,
    )

    for attempt in range(settings.max_retries + 1):
        try:
            upstream_request = client.build_request(
                method=method,
                url=upstream_url,
                params=params,
                headers=headers,
                content=body,
            )
            upstream_response = await client.send(upstream_request, stream=True)

            response_stream_mode = request_stream_mode or _response_is_streaming(upstream_response.headers)

            if (
                retries_allowed
                and upstream_response.status_code in retryable_statuses
                and attempt < settings.max_retries
            ):
                await upstream_response.aclose()
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue

            if response_stream_mode:
                logger.info(
                    "stream started method=%s path=/%s status=%s",
                    method,
                    upstream_path.lstrip("/"),
                    upstream_response.status_code,
                )
                return StreamingResponse(
                    content=_build_stream_generator(upstream_response, method, upstream_path, started_at),
                    status_code=upstream_response.status_code,
                    headers=_filtered_response_headers(upstream_response.headers),
                )

            content = await upstream_response.aread()
            await upstream_response.aclose()

            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "proxied method=%s path=/%s status=%s latency_ms=%s",
                method,
                upstream_path.lstrip("/"),
                upstream_response.status_code,
                elapsed_ms,
            )

            return Response(
                content=content,
                status_code=upstream_response.status_code,
                headers=_filtered_response_headers(upstream_response.headers),
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            if retries_allowed and attempt < settings.max_retries:
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue
            logger.warning("upstream timeout method=%s path=/%s type=%s error=%r", method, upstream_path, type(exc).__name__, exc)
            raise HTTPException(status_code=504, detail="Upstream timeout") from exc
        except httpx.RequestError as exc:
            if retries_allowed and attempt < settings.max_retries:
                backoff = settings.retry_backoff_base * (2**attempt)
                await asyncio.sleep(backoff)
                continue
            logger.error("upstream request error method=%s path=/%s type=%s error=%r", method, upstream_path, type(exc).__name__, exc)
            raise HTTPException(status_code=502, detail="Upstream request error") from exc

    # Теоретически недостижимая ветка, добавлена для явности.
    raise HTTPException(status_code=502, detail="Proxy error")
