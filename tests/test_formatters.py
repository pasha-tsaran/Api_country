from __future__ import annotations

import unittest
from datetime import datetime, timezone

from weather_bot.formatters import format_advanced, format_comparison, format_forecast
from weather_bot.models import CurrentWeather, Forecast, ForecastPoint, Location


LOCATION = Location("Москва", "RU", 55.75, 37.62, "Москва")


def make_current(location: Location = LOCATION, temperature: float = 12.4) -> CurrentWeather:
    return CurrentWeather(
        location=location,
        measured_at=1_700_000_000,
        timezone_offset=10_800,
        condition_id=800,
        description="ясно",
        temperature=temperature,
        feels_like=11.1,
        temp_min=10.0,
        temp_max=14.0,
        pressure=1013,
        humidity=60,
        visibility=10_000,
        wind_speed=3.2,
        wind_degrees=225,
        wind_gust=7.1,
        clouds=5,
        rain_1h=0.0,
        snow_1h=0.0,
        sunrise=1_699_950_000,
        sunset=1_699_985_000,
    )


class FormatterTests(unittest.TestCase):
    def test_forecast_is_grouped_into_at_most_five_days(self) -> None:
        start = int(datetime(2026, 9, 12, tzinfo=timezone.utc).timestamp())
        points = []
        for index in range(48):
            points.append(
                ForecastPoint(
                    timestamp=start + index * 10_800,
                    condition_id=800,
                    description="ясно",
                    temperature=10 + index / 10,
                    temp_min=9 + index / 10,
                    temp_max=11 + index / 10,
                    feels_like=10,
                    humidity=50,
                    wind_speed=2,
                    precipitation_probability=0.1,
                    rain_3h=0,
                    snow_3h=0,
                )
            )
        text = format_forecast(Forecast(LOCATION, 10_800, tuple(points)))
        self.assertEqual(text.count("☔ Вероятность"), 5)
        self.assertIn("ПРОГНОЗ НА 5 ДНЕЙ", text)

    def test_advanced_contains_optional_weather_details(self) -> None:
        text = format_advanced(make_current(), None)
        self.assertIn("Точка росы", text)
        self.assertIn("порывы 7.1 м/с", text)
        self.assertIn("Световой день", text)
        self.assertIn("Качество воздуха: нет данных", text)

    def test_comparison_reports_warmer_city(self) -> None:
        other = Location("Сочи", "RU", 43.6, 39.7)
        text = format_comparison(make_current(temperature=4), make_current(other, 14))
        self.assertIn("СРАВНЕНИЕ ПОГОДЫ", text)
        self.assertIn("🔵 Москва: +4°C", text)
        self.assertIn("🟢 Сочи: +14°C", text)
        self.assertNotIn("│", text)
        self.assertIn("В городе Сочи теплее на 10.0°C", text)


if __name__ == "__main__":
    unittest.main()
