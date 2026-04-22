"""Настройка логирования приложения с ротацией файлов."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Инициализирует логирование в stdout и файл с ротацией."""

    os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Уменьшаем шум от uvicorn access-логов, чтобы фокус был на служебных сообщениях.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
