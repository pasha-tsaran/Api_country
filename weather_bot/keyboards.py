"""JSON-клавиатуры VK. Транспорт может отправлять их без знания сценариев."""

from __future__ import annotations

import json
from enum import Enum


class KeyboardKind(str, Enum):
    MAIN = "main"
    LOCATION = "location"
    CITY = "city"
    FORM = "form"


def _text_button(label: str, command: str, color: str) -> dict:
    return {
        "action": {
            "type": "text",
            "label": label,
            "payload": json.dumps({"command": command}, ensure_ascii=False),
        },
        "color": color,
    }


def main_keyboard() -> str:
    """Главное меню 2×3 в стиле предоставленного макета."""

    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                _text_button("🌤 Сейчас", "current", "secondary"),
                _text_button("📅 На 5 дней", "forecast", "secondary"),
            ],
            [
                _text_button("📌 Мой город", "city_settings", "positive"),
                _text_button("📍 На карте", "location", "positive"),
            ],
            [
                _text_button("🌡 Подробнее", "advanced", "secondary"),
                _text_button("⚖ Сравнить", "compare", "secondary"),
            ],
            [_text_button("🐞 Сообщить об ошибке", "report_error", "primary")],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def location_keyboard() -> str:
    """Системная кнопка VK запрашивает координаты только с согласия пользователя."""

    keyboard = {
        "one_time": True,
        "inline": False,
        "buttons": [
            [{"action": {"type": "location", "payload": '{"command":"location"}'}}],
            [_text_button("↩ Назад", "menu", "secondary")],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def city_keyboard() -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                _text_button("✏ Изменить", "set_city", "primary"),
                _text_button("🗑 Отвязать", "unset_city", "negative"),
            ],
            [_text_button("↩ В меню", "menu", "secondary")],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def form_keyboard() -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [[_text_button("❌ Отменить", "menu", "secondary")]],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def get_keyboard(kind: KeyboardKind) -> str:
    keyboards = {
        KeyboardKind.MAIN: main_keyboard,
        KeyboardKind.LOCATION: location_keyboard,
        KeyboardKind.CITY: city_keyboard,
        KeyboardKind.FORM: form_keyboard,
    }
    return keyboards[kind]()
