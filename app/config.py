"""Конфигурация приложения из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Настройки прокси-сервиса."""

    openai_base_url: str
    request_timeout_connect: float
    request_timeout_read: float
    request_timeout_write: float
    request_timeout_pool: float
    max_retries: int
    retry_backoff_base: float
    retry_idempotent_only: bool
    log_level: str
    log_file: str
    log_max_bytes: int
    log_backup_count: int
    show_proxy_status_only: bool
    host: str
    port: int


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    """Считывает настройки из окружения с безопасными значениями по умолчанию."""

    return Settings(
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/"),
        request_timeout_connect=float(os.getenv("REQUEST_TIMEOUT_CONNECT", "10")),
        request_timeout_read=float(os.getenv("REQUEST_TIMEOUT_READ", "300")),
        request_timeout_write=float(os.getenv("REQUEST_TIMEOUT_WRITE", "30")),
        request_timeout_pool=float(os.getenv("REQUEST_TIMEOUT_POOL", "10")),
        max_retries=int(os.getenv("MAX_RETRIES", "0")),
        retry_backoff_base=float(os.getenv("RETRY_BACKOFF_BASE", "0.4")),
        retry_idempotent_only=_get_bool("RETRY_IDEMPOTENT_ONLY", True),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "logs/app.log"),
        log_max_bytes=int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        show_proxy_status_only=_get_bool("SHOW_PROXY_STATUS_ONLY", True),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
