from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from weather_bot.config import load_settings


class ConfigTests(unittest.TestCase):
    @patch("weather_bot.config.load_dotenv")
    def test_group_id_accepts_vk_club_prefix(self, _load_dotenv) -> None:
        environment = {
            "VK_GROUP_TOKEN": "token",
            "VK_GROUP_ID": "club241444817",
            "OPENWEATHER_API_KEY": "weather-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()
        self.assertEqual(settings.vk_group_id, 241444817)
        self.assertEqual(settings.database_path, "data/weather_bot.sqlite3")
        self.assertIsNone(settings.feedback_recipient)

    @patch("weather_bot.config.load_dotenv")
    def test_feedback_recipient_accepts_screen_name(self, _load_dotenv) -> None:
        environment = {
            "VK_GROUP_TOKEN": "token",
            "VK_GROUP_ID": "1",
            "OPENWEATHER_API_KEY": "weather-key",
            "VK_FEEDBACK_PEER_ID": "https://vk.com/paha_kenai/",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()
        self.assertEqual(settings.feedback_recipient, "paha_kenai")


if __name__ == "__main__":
    unittest.main()
