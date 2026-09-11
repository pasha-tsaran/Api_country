from __future__ import annotations

import logging
import unittest
from pathlib import Path

from weather_bot.database import (
    Database,
    DatabaseLogHandler,
    DialogHistoryStore,
    SqliteFeedbackStore,
    SqliteUserStore,
)
from weather_bot.models import Location
from weather_bot.storage import Action


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_path = Path(__file__).with_name("_test_weather.sqlite3")
        self._remove_database_files()
        self.database = Database(self.database_path)
        self.database.create_schema()

    def tearDown(self) -> None:
        self.database.close()
        self._remove_database_files()

    def _remove_database_files(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            self.database_path.with_name(self.database_path.name + suffix).unlink(
                missing_ok=True
            )

    def test_user_city_and_pending_action_are_persistent(self) -> None:
        store = SqliteUserStore(self.database)
        city = Location("Москва", "RU", 55.75, 37.62)
        store.set_home_city(10, city)
        store.set_pending(10, Action.FORECAST)

        restored = store.get(10)
        self.assertEqual(restored.home_city, city)
        self.assertIs(restored.pending, Action.FORECAST)

        store.clear_home_city(10)
        self.assertIsNone(store.get(10).home_city)

    def test_feedback_history_and_logs_are_written(self) -> None:
        feedback = SqliteFeedbackStore(self.database)
        feedback_id = feedback.create(10, 10, "Описание проблемы")
        self.assertEqual(feedback_id, 1)

        history = DialogHistoryStore(self.database)
        history.record(
            user_id=10,
            peer_id=10,
            direction="incoming",
            text="Привет",
        )
        self.assertEqual(history.recent(10)[0].text, "Привет")

        handler = DatabaseLogHandler(self.database)
        record = logging.LogRecord(
            "weather_bot.test", logging.INFO, __file__, 1, "Бот запущен", (), None
        )
        handler.emit(record)
        with self.database.connect() as connection:
            saved = connection.execute(
                "SELECT message FROM application_logs LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(saved)
        self.assertEqual(saved["message"], "Бот запущен")


if __name__ == "__main__":
    unittest.main()
