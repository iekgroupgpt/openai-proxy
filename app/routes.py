"""Маршруты FastAPI для проксирования OpenAI-совместимых эндпоинтов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.proxy import proxy_request


# Зависимости подставляются из main.py, чтобы избежать глобального состояния.
def get_settings_dep() -> Settings:
    raise RuntimeError("Settings dependency is not configured")


def get_client_dep():
    raise RuntimeError("Client dependency is not configured")


def create_router() -> APIRouter:
    """Создает роутер с явными и универсальными OpenAI-маршрутами."""

    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> JSONResponse:
        """Быстрый liveness-check без внешних зависимостей."""
        return JSONResponse({"status": "ok"})

    @router.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        client=Depends(get_client_dep),
    ):
        return await proxy_request(request, settings, client, "v1/chat/completions")

    @router.post("/v1/embeddings")
    async def embeddings(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        client=Depends(get_client_dep),
    ):
        return await proxy_request(request, settings, client, "v1/embeddings")

    @router.post("/v1/responses")
    async def responses(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        client=Depends(get_client_dep),
    ):
        return await proxy_request(request, settings, client, "v1/responses")

    @router.get("/v1/models")
    async def models(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        client=Depends(get_client_dep),
    ):
        return await proxy_request(request, settings, client, "v1/models")

    @router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def v1_catch_all(
        path: str,
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        client=Depends(get_client_dep),
    ):
        """Универсальный fallback для дополнительных v1-эндпоинтов OpenAI."""
        return await proxy_request(request, settings, client, f"v1/{path}")

    return router
