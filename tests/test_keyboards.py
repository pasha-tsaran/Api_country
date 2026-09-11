from __future__ import annotations

import json
import unittest

from weather_bot.keyboards import city_keyboard, form_keyboard, location_keyboard, main_keyboard


class KeyboardTests(unittest.TestCase):
    def test_main_keyboard_has_seven_buttons_in_four_rows(self) -> None:
        keyboard = json.loads(main_keyboard())
        self.assertEqual([len(row) for row in keyboard["buttons"]], [2, 2, 2, 1])
        commands = {
            json.loads(button["action"]["payload"])["command"]
            for row in keyboard["buttons"]
            for button in row
        }
        self.assertEqual(
            commands,
            {
                "current",
                "forecast",
                "city_settings",
                "location",
                "advanced",
                "compare",
                "report_error",
            },
        )
        labels = [
            button["action"]["label"]
            for row in keyboard["buttons"]
            for button in row
        ]
        self.assertLessEqual(max(map(len, labels)), 24)

    def test_location_keyboard_requests_native_location(self) -> None:
        keyboard = json.loads(location_keyboard())
        self.assertEqual(keyboard["buttons"][0][0]["action"]["type"], "location")

    def test_city_and_form_keyboards_have_navigation(self) -> None:
        city = json.loads(city_keyboard())
        form = json.loads(form_keyboard())
        city_commands = {
            json.loads(button["action"]["payload"])["command"]
            for row in city["buttons"]
            for button in row
        }
        self.assertEqual(city_commands, {"set_city", "unset_city", "menu"})
        self.assertEqual(
            json.loads(form["buttons"][0][0]["action"]["payload"])["command"],
            "menu",
        )


if __name__ == "__main__":
    unittest.main()
