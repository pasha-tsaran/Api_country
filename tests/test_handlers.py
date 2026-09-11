from __future__ import annotations

import unittest

from weather_bot.handlers import IncomingMessage, MessageHandler
from weather_bot.keyboards import KeyboardKind
from weather_bot.models import AirQuality, Forecast, Location
from weather_bot.storage import Action, MemoryFeedbackStore, MemoryUserStore
from tests.test_formatters import make_current


class FakeService:
    def __init__(self) -> None:
        self.locations = {
            "москва": Location("Москва", "RU", 55.75, 37.62),
            "сочи": Location("Сочи", "RU", 43.6, 39.7),
        }

    def resolve_city(self, city: str) -> Location:
        return self.locations[city.casefold()]

    def resolve_coordinates(self, latitude: float, longitude: float) -> Location:
        return Location("Тула", "RU", latitude, longitude)

    def current(self, location: Location):
        temperature = 18 if location.name == "Сочи" else 8
        return make_current(location, temperature)

    def forecast(self, location: Location) -> Forecast:
        return Forecast(location, 0, ())

    def air_quality(self, location: Location) -> AirQuality:
        return AirQuality(1, 4.2, 8.1)


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryUserStore()
        self.feedback = MemoryFeedbackStore()
        self.handler = MessageHandler(
            FakeService(),  # type: ignore[arg-type]
            self.store,
            self.feedback,
            feedback_peer_id=999,
        )

    def test_home_city_flow_and_default_weather(self) -> None:
        prompt = self.handler.handle(
            IncomingMessage(1, payload={"command": Action.SET_CITY.value})
        )
        self.assertIn("основного города", prompt.text)
        saved = self.handler.handle(IncomingMessage(1, text="Москва"))
        self.assertIn("Основной город сохранён", saved.text)

        weather = self.handler.handle(
            IncomingMessage(1, payload={"command": Action.CURRENT.value})
        )
        self.assertIn("ПОГОДА СЕЙЧАС", weather.text)
        self.assertIn("Москва", weather.text)

    def test_home_city_can_be_unlinked(self) -> None:
        self.handler.handle(IncomingMessage(1, payload={"command": "set_city"}))
        self.handler.handle(IncomingMessage(1, text="Москва"))

        settings = self.handler.handle(
            IncomingMessage(1, payload={"command": "city_settings"})
        )
        self.assertIs(settings.keyboard, KeyboardKind.CITY)
        removed = self.handler.handle(
            IncomingMessage(1, payload={"command": "unset_city"})
        )
        self.assertIn("отвязан", removed.text)
        self.assertIsNone(self.store.get(1).home_city)

    def test_compare_requires_two_cities_and_keeps_state(self) -> None:
        self.handler.handle(IncomingMessage(2, payload={"command": "compare"}))
        invalid = self.handler.handle(IncomingMessage(2, text="Москва"))
        self.assertIn("через символ |", invalid.text)
        self.assertIs(self.store.get(2).pending, Action.COMPARE)

        result = self.handler.handle(IncomingMessage(2, text="Москва | Сочи"))
        self.assertIn("СРАВНЕНИЕ ПОГОДЫ", result.text)
        self.assertIsNone(self.store.get(2).pending)

    def test_location_uses_special_keyboard_then_coordinates(self) -> None:
        prompt = self.handler.handle(
            IncomingMessage(3, payload='{"command": "location"}')
        )
        self.assertIs(prompt.keyboard, KeyboardKind.LOCATION)

        result = self.handler.handle(
            IncomingMessage(3, latitude=54.2, longitude=37.6)
        )
        self.assertIn("ближайший населённый пункт", result.text)
        self.assertIn("Тула", result.text)

    def test_plain_city_name_shows_current_weather(self) -> None:
        result = self.handler.handle(IncomingMessage(4, text="Сочи"))
        self.assertIn("+18°C", result.text)

    def test_feedback_is_saved_and_creates_owner_notification(self) -> None:
        prompt = self.handler.handle(
            IncomingMessage(5, peer_id=5, payload={"command": "report_error"})
        )
        self.assertIs(prompt.keyboard, KeyboardKind.FORM)

        result = self.handler.handle(
            IncomingMessage(5, peer_id=5, text="Не открывается прогноз на пять дней")
        )
        self.assertIn("Обращение #1", result.text)
        self.assertEqual(self.feedback.items[0][2], "Не открывается прогноз на пять дней")
        self.assertEqual(result.notifications[0].peer_id, 999)
        self.assertIn("[id5|пользователь VK]", result.notifications[0].text)


if __name__ == "__main__":
    unittest.main()
