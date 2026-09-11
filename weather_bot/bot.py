"""VK Long Poll транспорт и сборка зависимостей приложения."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.utils import get_random_id

from weather_bot.config import ConfigError, load_settings
from weather_bot.database import (
    Database,
    DatabaseLogHandler,
    DialogHistoryStore,
    SqliteFeedbackStore,
    SqliteUserStore,
)
from weather_bot.handlers import IncomingMessage, MessageHandler
from weather_bot.keyboards import KeyboardKind, get_keyboard
from weather_bot.openweather import OpenWeatherClient
from weather_bot.service import WeatherService

LOGGER = logging.getLogger(__name__)


class VkWeatherBot:
    def __init__(
        self,
        token: str,
        group_id: int,
        handler: MessageHandler,
        history: DialogHistoryStore,
    ) -> None:
        self._session = vk_api.VkApi(token=token)
        self._api = self._session.get_api()
        self._group_id = group_id
        self._handler = handler
        self._history = history

    def run_forever(self) -> None:
        LOGGER.info("VK Weather Bot запущен")
        while True:
            try:
                long_poll = VkBotLongPoll(self._session, self._group_id)
                for event in long_poll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._process_event(event)
            except (requests.RequestException, vk_api.ApiError) as error:
                LOGGER.warning("Соединение с VK потеряно: %s; повтор через 5 секунд", error)
                time.sleep(5)

    def _process_event(self, event: Any) -> None:
        message = event.object.message
        if message.get("out"):
            return
        incoming = _to_incoming(message)
        peer_id = int(message["peer_id"])
        try:
            self._record_history(
                user_id=incoming.user_id,
                peer_id=peer_id,
                direction="incoming",
                text=incoming.text,
                details={
                    "payload": incoming.payload,
                    "latitude": incoming.latitude,
                    "longitude": incoming.longitude,
                },
            )
            reply = self._handler.handle(incoming)
        except Exception:
            LOGGER.exception("Необработанная ошибка для пользователя %s", incoming.user_id)
            self._send(
                peer_id,
                "Произошла внутренняя ошибка. Попробуйте ещё раз чуть позже.",
                get_keyboard(KeyboardKind.MAIN),
            )
            return
        self._send(peer_id, reply.text, get_keyboard(reply.keyboard))
        self._record_history(
            user_id=incoming.user_id,
            peer_id=peer_id,
            direction="outgoing",
            text=reply.text,
            details={"keyboard": reply.keyboard.value},
        )
        for notification in reply.notifications:
            try:
                self._send(notification.peer_id, notification.text)
                self._record_history(
                    user_id=incoming.user_id,
                    peer_id=notification.peer_id,
                    direction="notification",
                    text=notification.text,
                    details={"kind": "feedback"},
                )
            except vk_api.ApiError:
                LOGGER.exception(
                    "Не удалось отправить обращение пользователя %s получателю %s",
                    incoming.user_id,
                    notification.peer_id,
                )

    def _record_history(self, **values: Any) -> None:
        try:
            self._history.record(**values)
        except sqlite3.Error:
            LOGGER.exception("Не удалось записать историю диалога")

    def _send(self, peer_id: int, text: str, keyboard: str | None = None) -> None:
        params: dict[str, Any] = {
            "peer_id": peer_id,
            "message": text[:4096],
            "random_id": get_random_id(),
        }
        if keyboard is not None:
            params["keyboard"] = keyboard
        self._api.messages.send(**params)


def _to_incoming(message: Any) -> IncomingMessage:
    latitude = longitude = None
    geo = message.get("geo") or {}
    coordinates = geo.get("coordinates") or {}
    try:
        if "latitude" in coordinates and "longitude" in coordinates:
            latitude = float(coordinates["latitude"])
            longitude = float(coordinates["longitude"])
    except (TypeError, ValueError):
        LOGGER.info("VK прислал некорректные координаты")

    return IncomingMessage(
        user_id=int(message["from_id"]),
        peer_id=int(message["peer_id"]),
        text=str(message.get("text") or ""),
        payload=message.get("payload"),
        latitude=latitude,
        longitude=longitude,
    )


def run() -> None:
    try:
        settings = load_settings()
    except ConfigError as error:
        raise SystemExit(f"Ошибка конфигурации: {error}") from error

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        feedback_peer_id = _resolve_feedback_recipient(
            settings.vk_group_token,
            settings.feedback_recipient,
        )
    except (ConfigError, requests.RequestException, vk_api.ApiError) as error:
        raise SystemExit(f"Ошибка получателя обратной связи: {error}") from error

    try:
        database = Database(settings.database_path)
        database.create_schema()
    except (OSError, sqlite3.Error) as error:
        LOGGER.error("Не удалось открыть SQLite: %s", error.__class__.__name__)
        raise SystemExit("Ошибка базы данных: проверьте DATABASE_PATH") from error

    logging.getLogger().addHandler(DatabaseLogHandler(database))
    client = OpenWeatherClient(settings.openweather_api_key)
    service = WeatherService(client)
    history = DialogHistoryStore(database)
    handler = MessageHandler(
        service,
        SqliteUserStore(database),
        SqliteFeedbackStore(database),
        feedback_peer_id,
    )
    try:
        VkWeatherBot(
            settings.vk_group_token,
            settings.vk_group_id,
            handler,
            history,
        ).run_forever()
    finally:
        database.close()


def _resolve_feedback_recipient(
    token: str,
    recipient: int | str | None,
) -> int | None:
    if recipient is None or isinstance(recipient, int):
        return recipient
    session = vk_api.VkApi(token=token)
    result = session.method(
        "utils.resolveScreenName",
        {"screen_name": recipient},
    )
    if not result or result.get("type") != "user":
        raise ConfigError(f"Аккаунт VK «{recipient}» не найден")
    return int(result["object_id"])
