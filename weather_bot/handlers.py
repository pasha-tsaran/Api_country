"""Диалоговые сценарии бота, не зависящие от библиотеки VK."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from weather_bot.formatters import (
    format_advanced,
    format_comparison,
    format_current,
    format_forecast,
)
from weather_bot.keyboards import KeyboardKind
from weather_bot.models import Location
from weather_bot.openweather import WeatherError
from weather_bot.service import WeatherService
from weather_bot.storage import (
    Action,
    FeedbackStore,
    MemoryFeedbackStore,
    UserStore,
)

WELCOME = (
    "Привет! Я покажу погоду в любой точке мира 🌍\n\n"
    "Выберите действие на клавиатуре или просто отправьте название города."
)


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    user_id: int
    peer_id: int | None = None
    text: str = ""
    payload: str | dict[str, Any] | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class BotReply:
    text: str
    keyboard: KeyboardKind = KeyboardKind.MAIN
    notifications: tuple["BotNotification", ...] = ()


@dataclass(frozen=True, slots=True)
class BotNotification:
    peer_id: int
    text: str


class MessageHandler:
    def __init__(
        self,
        service: WeatherService,
        store: UserStore,
        feedback_store: FeedbackStore | None = None,
        feedback_peer_id: int | None = None,
    ) -> None:
        self._service = service
        self._store = store
        self._feedback = feedback_store or MemoryFeedbackStore()
        self._feedback_peer_id = feedback_peer_id

    def handle(self, message: IncomingMessage) -> BotReply:
        try:
            if message.latitude is not None and message.longitude is not None:
                return self._weather_at_coordinates(message)

            text = " ".join(message.text.split())
            command = _extract_command(message.payload) or _text_command(text)

            if command == "menu" or text.casefold() in {
                "начать",
                "старт",
                "/start",
                "меню",
            }:
                self._store.set_pending(message.user_id, None)
                return BotReply(WELCOME)
            if command == "city_settings":
                return self._city_settings(message.user_id)
            if command == "unset_city":
                return self._unset_home_city(message.user_id)
            if command in {action.value for action in Action}:
                return self._start_action(message.user_id, Action(command))

            state = self._store.get(message.user_id)
            if not text:
                return BotReply("Не вижу текста. Выберите действие на клавиатуре.")
            if state.pending is Action.SET_CITY:
                return self._set_home_city(message.user_id, text)
            if state.pending is Action.COMPARE:
                return self._compare(message.user_id, text)
            if state.pending is Action.REPORT_ERROR:
                return self._save_feedback(message, text)
            if state.pending is Action.LOCATION:
                return BotReply(
                    "Нажмите системную кнопку «Отправить местоположение» "
                    "ниже или вернитесь в меню.",
                    KeyboardKind.LOCATION,
                )
            if state.pending in {Action.CURRENT, Action.FORECAST, Action.ADVANCED}:
                return self._show_for_city(message.user_id, state.pending, text)

            # Естественный сценарий: сообщение с названием города показывает погоду.
            return self._show_for_city(message.user_id, Action.CURRENT, text)
        except WeatherError as error:
            return BotReply(f"⚠️ {error}\n\nПопробуйте ещё раз или выберите другое действие.")

    def _start_action(self, user_id: int, action: Action) -> BotReply:
        state = self._store.get(user_id)
        if action is Action.SET_CITY:
            self._store.set_pending(user_id, action)
            current = f" Сейчас выбран: {state.home_city.title}." if state.home_city else ""
            return BotReply(
                f"📌 Напишите название основного города.{current}",
                KeyboardKind.FORM,
            )
        if action is Action.COMPARE:
            self._store.set_pending(user_id, action)
            return BotReply(
                "⚖ Напишите два города через вертикальную черту.\n"
                "Например: Москва | Санкт-Петербург"
            )
        if action is Action.LOCATION:
            self._store.set_pending(user_id, action)
            return BotReply(
                "📍 Нажмите кнопку ниже и разрешите VK отправить точку на карте.\n"
                "Местоположение не сохраняется.",
                KeyboardKind.LOCATION,
            )
        if action is Action.REPORT_ERROR:
            self._store.set_pending(user_id, action)
            return BotReply(
                "🐞 СООБЩИТЬ ОБ ОШИБКЕ\n\n"
                "Опишите проблему одним сообщением:\n"
                "• что вы пытались сделать;\n"
                "• что произошло;\n"
                "• какой результат ожидали.\n\n"
                "Обращение сохранится и будет передано владельцу бота.",
                KeyboardKind.FORM,
            )

        self._store.set_pending(user_id, action)
        if state.home_city is None:
            labels = {
                Action.CURRENT: "текущую погоду",
                Action.FORECAST: "прогноз",
                Action.ADVANCED: "расширенные данные",
            }
            return BotReply(f"Введите город, чтобы посмотреть {labels[action]}.")

        reply = self._show_for_location(action, state.home_city)
        return BotReply(
            reply + "\n\nЧтобы проверить другой город, просто отправьте его название."
        )

    def _set_home_city(self, user_id: int, city: str) -> BotReply:
        location = self._service.resolve_city(city)
        self._store.set_home_city(user_id, location)
        return BotReply(
            f"✅ Основной город сохранён: {location.title}.\n\n"
            "Теперь кнопки погоды используют его автоматически."
        )

    def _city_settings(self, user_id: int) -> BotReply:
        state = self._store.get(user_id)
        self._store.set_pending(user_id, None)
        if state.home_city is None:
            self._store.set_pending(user_id, Action.SET_CITY)
            return BotReply(
                "📌 Основной город пока не указан.\n\n"
                "Напишите его название, например: Екатеринбург.",
                KeyboardKind.FORM,
            )
        return BotReply(
            f"📌 Ваш основной город: {state.home_city.title}.\n\n"
            "Его можно изменить или отвязать.",
            KeyboardKind.CITY,
        )

    def _unset_home_city(self, user_id: int) -> BotReply:
        state = self._store.get(user_id)
        if state.home_city is None:
            return BotReply("Основной город уже не указан.")
        city_name = state.home_city.title
        self._store.clear_home_city(user_id)
        return BotReply(
            f"✅ Город {city_name} отвязан.\n\n"
            "Теперь бот будет спрашивать город перед запросом погоды."
        )

    def _save_feedback(self, message: IncomingMessage, text: str) -> BotReply:
        if len(text) < 5:
            return BotReply(
                "Опишите проблему чуть подробнее — минимум 5 символов.",
                KeyboardKind.FORM,
            )
        if len(text) > 2_000:
            return BotReply(
                "Сообщение слишком длинное. Сократите его до 2000 символов.",
                KeyboardKind.FORM,
            )

        source_peer_id = message.peer_id or message.user_id
        feedback_id = self._feedback.create(message.user_id, source_peer_id, text)
        self._store.set_pending(message.user_id, None)
        notifications: tuple[BotNotification, ...] = ()
        if self._feedback_peer_id is not None:
            notification = BotNotification(
                peer_id=self._feedback_peer_id,
                text=(
                    f"🐞 НОВОЕ ОБРАЩЕНИЕ #{feedback_id}\n\n"
                    f"От: [id{message.user_id}|пользователь VK]\n"
                    f"ID пользователя: {message.user_id}\n"
                    f"Диалог: {source_peer_id}\n\n"
                    f"{text}"
                ),
            )
            notifications = (notification,)

        delivery = (
            "сохранено и отправлено владельцу"
            if notifications
            else "сохранено для владельца"
        )
        return BotReply(
            f"✅ Спасибо! Обращение #{feedback_id} {delivery}.",
            notifications=notifications,
        )

    def _show_for_city(self, user_id: int, action: Action, city: str) -> BotReply:
        location = self._service.resolve_city(city)
        text = self._show_for_location(action, location)
        self._store.set_pending(user_id, None)
        return BotReply(text)

    def _show_for_location(self, action: Action, location: Location) -> str:
        if action is Action.FORECAST:
            return format_forecast(self._service.forecast(location))
        current = self._service.current(location)
        if action is Action.ADVANCED:
            return format_advanced(current, self._service.air_quality(location))
        return format_current(current)

    def _weather_at_coordinates(self, message: IncomingMessage) -> BotReply:
        assert message.latitude is not None and message.longitude is not None
        location = self._service.resolve_coordinates(message.latitude, message.longitude)
        current = self._service.current(location)
        self._store.set_pending(message.user_id, None)
        return BotReply(
            "📍 Нашёл ближайший населённый пункт.\n\n" + format_current(current)
        )

    def _compare(self, user_id: int, text: str) -> BotReply:
        cities = _split_cities(text)
        if cities is None:
            return BotReply(
                "Нужны два города через символ |.\nНапример: Казань | Сочи"
            )
        left_location = self._service.resolve_city(cities[0])
        right_location = self._service.resolve_city(cities[1])
        left = self._service.current(left_location)
        right = self._service.current(right_location)
        self._store.set_pending(user_id, None)
        return BotReply(format_comparison(left, right))


def _extract_command(payload: str | dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (json.JSONDecodeError, TypeError):
        return None
    command = data.get("command") if isinstance(data, dict) else None
    return str(command) if command is not None else None


def _text_command(text: str) -> str | None:
    normalized = text.casefold()
    labels = {
        "🌤 сейчас": Action.CURRENT.value,
        "🌤 погода сейчас": Action.CURRENT.value,
        "погода сейчас": Action.CURRENT.value,
        "📅 на 5 дней": Action.FORECAST.value,
        "📅 прогноз 5 дней": Action.FORECAST.value,
        "прогноз на 5 дней": Action.FORECAST.value,
        "📌 мой город": "city_settings",
        "мой город": "city_settings",
        "✏ изменить": Action.SET_CITY.value,
        "🗑 отвязать": "unset_city",
        "📍 на карте": Action.LOCATION.value,
        "📍 геолокация": Action.LOCATION.value,
        "геолокация": Action.LOCATION.value,
        "🌡 подробнее": Action.ADVANCED.value,
        "🌡 расширенный режим": Action.ADVANCED.value,
        "расширенный режим": Action.ADVANCED.value,
        "⚖ сравнить": Action.COMPARE.value,
        "⚖ сравнить города": Action.COMPARE.value,
        "сравнить города": Action.COMPARE.value,
        "🐞 сообщить об ошибке": Action.REPORT_ERROR.value,
        "сообщить об ошибке": Action.REPORT_ERROR.value,
        "❌ отменить": "menu",
        "↩ назад": "menu",
        "↩ в меню": "menu",
    }
    return labels.get(normalized)


def _split_cities(text: str) -> tuple[str, str] | None:
    separator = "|" if "|" in text else ";" if ";" in text else None
    if separator is None:
        return None
    parts = [part.strip() for part in text.split(separator)]
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]
