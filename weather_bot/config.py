"""Загрузка и проверка конфигурации приложения."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Ошибка пользовательской конфигурации."""


@dataclass(frozen=True, slots=True)
class Settings:
    vk_group_token: str
    vk_group_id: int
    openweather_api_key: str
    database_path: str
    feedback_recipient: int | str | None = None
    log_level: str = "INFO"


def load_settings() -> Settings:
    """Прочитать `.env` и вернуть проверенные настройки.

    Старое имя ``API_KEY`` поддерживается для совместимости с исходным проектом.
    """

    load_dotenv()
    vk_token = os.getenv("VK_GROUP_TOKEN", "").strip()
    group_id_raw = os.getenv("VK_GROUP_ID", "").strip()
    weather_key = (
        os.getenv("OPENWEATHER_API_KEY", "").strip()
        or os.getenv("API_KEY", "").strip()
    )

    missing = []
    if not vk_token:
        missing.append("VK_GROUP_TOKEN")
    if not group_id_raw:
        missing.append("VK_GROUP_ID")
    if not weather_key:
        missing.append("OPENWEATHER_API_KEY")
    if missing:
        raise ConfigError(
            "Добавьте в .env обязательные переменные: " + ", ".join(missing)
        )

    normalized_group_id = group_id_raw.casefold()
    for prefix in ("club", "public"):
        if normalized_group_id.startswith(prefix):
            normalized_group_id = normalized_group_id.removeprefix(prefix)
            break
    normalized_group_id = normalized_group_id.lstrip("-")
    try:
        group_id = int(normalized_group_id)
    except ValueError as error:
        raise ConfigError(
            "VK_GROUP_ID должен быть числом или иметь вид club123456"
        ) from error
    if group_id <= 0:
        raise ConfigError("VK_GROUP_ID должен быть положительным числом")

    database_path = os.getenv("DATABASE_PATH", "data/weather_bot.sqlite3").strip()
    if not database_path:
        raise ConfigError("DATABASE_PATH не может быть пустым")

    feedback_peer_raw = (
        os.getenv("VK_FEEDBACK_PEER_ID", "").strip()
        or os.getenv("VK_ADMIN_ID", "").strip()
    )
    feedback_recipient: int | str | None = None
    if feedback_peer_raw:
        try:
            feedback_recipient = int(feedback_peer_raw)
        except ValueError:
            screen_name = feedback_peer_raw.removeprefix("@").rstrip("/").rsplit("/", 1)[-1]
            if not re.fullmatch(r"[A-Za-z0-9_.]+", screen_name):
                raise ConfigError(
                    "VK_FEEDBACK_PEER_ID должен быть ID или коротким адресом VK"
                )
            feedback_recipient = screen_name
    if isinstance(feedback_recipient, int) and feedback_recipient <= 0:
        raise ConfigError("VK_FEEDBACK_PEER_ID должен быть положительным числом")

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    return Settings(
        vk_token,
        group_id,
        weather_key,
        database_path,
        feedback_recipient,
        log_level,
    )
