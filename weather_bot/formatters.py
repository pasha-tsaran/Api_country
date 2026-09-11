"""Преобразование погодных моделей в компактные красивые сообщения VK."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from weather_bot.models import AirQuality, CurrentWeather, Forecast, ForecastPoint

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
AQI_LABELS = {
    1: "хорошее 🟢",
    2: "нормальное 🟡",
    3: "среднее 🟠",
    4: "плохое 🔴",
    5: "очень плохое 🟣",
}


def weather_icon(condition_id: int) -> str:
    if 200 <= condition_id < 300:
        return "⛈"
    if 300 <= condition_id < 600:
        return "🌧"
    if 600 <= condition_id < 700:
        return "🌨"
    if 700 <= condition_id < 800:
        return "🌫"
    if condition_id == 800:
        return "☀️"
    if condition_id == 801:
        return "🌤"
    if 802 <= condition_id < 900:
        return "☁️"
    return "🌡"


def format_current(weather: CurrentWeather) -> str:
    local_time = _local_datetime(weather.measured_at, weather.timezone_offset)
    return (
        f"{weather_icon(weather.condition_id)} ПОГОДА СЕЙЧАС\n"
        f"📍 {weather.location.title}\n\n"
        f"{_temp(weather.temperature)} · {weather.description.capitalize()}\n"
        f"Ощущается как {_temp(weather.feels_like)}\n\n"
        f"💧 Влажность: {weather.humidity}%\n"
        f"💨 Ветер: {_number(weather.wind_speed)} м/с\n"
        f"🧭 Давление: {round(weather.pressure * 0.750062)} мм рт. ст.\n\n"
        f"Обновлено: {local_time:%H:%M} по местному времени"
    )


def format_forecast(forecast: Forecast) -> str:
    days = _summarize_days(forecast)
    blocks = [f"📅 ПРОГНОЗ НА 5 ДНЕЙ\n📍 {forecast.location.title}"]
    for day in days:
        blocks.append(
            f"{WEEKDAYS[day.day.weekday()]}, {day.day:%d.%m}  "
            f"{weather_icon(day.condition_id)} {day.description.capitalize()}\n"
            f"🌡 {_temp(day.minimum)}…{_temp(day.maximum)}  ·  "
            f"💧 {day.humidity}%  ·  💨 {_number(day.wind_speed)} м/с\n"
            f"☔ Вероятность {round(day.pop * 100)}% · осадки {_number(day.precipitation)} мм"
        )
    return "\n\n".join(blocks)


def format_advanced(weather: CurrentWeather, air: AirQuality | None) -> str:
    wind = f"{_number(weather.wind_speed)} м/с, {_wind_direction(weather.wind_degrees)}"
    if weather.wind_gust is not None:
        wind += f"; порывы {_number(weather.wind_gust)} м/с"

    visibility = (
        f"{_number(weather.visibility / 1000)} км"
        if weather.visibility is not None
        else "нет данных"
    )
    precipitation = weather.rain_1h + weather.snow_1h
    sunrise = _format_time(weather.sunrise, weather.timezone_offset)
    sunset = _format_time(weather.sunset, weather.timezone_offset)
    daylight = _daylight(weather.sunrise, weather.sunset)
    dew_point = _dew_point(weather.temperature, weather.humidity)
    air_text = "нет данных"
    if air is not None:
        particles = []
        if air.pm2_5 is not None:
            particles.append(f"PM2.5 {_number(air.pm2_5)}")
        if air.pm10 is not None:
            particles.append(f"PM10 {_number(air.pm10)}")
        suffix = f" ({', '.join(particles)} мкг/м³)" if particles else ""
        air_text = AQI_LABELS.get(air.index, f"индекс {air.index}") + suffix

    return (
        f"🌡 РАСШИРЕННЫЙ РЕЖИМ\n"
        f"📍 {weather.location.title}\n\n"
        f"{weather_icon(weather.condition_id)} {weather.description.capitalize()}\n"
        f"🌡 Температура: {_temp(weather.temperature)}\n"
        f"🤍 Ощущается: {_temp(weather.feels_like)}\n"
        f"↕ Сейчас по району: {_temp(weather.temp_min)}…{_temp(weather.temp_max)}\n"
        f"💧 Влажность: {weather.humidity}%\n"
        f"💦 Точка росы: {_temp(dew_point) if dew_point is not None else 'нет данных'}\n"
        f"🧭 Давление: {weather.pressure} гПа / "
        f"{round(weather.pressure * 0.750062)} мм рт. ст.\n"
        f"💨 Ветер: {wind}\n"
        f"👁 Видимость: {visibility}\n"
        f"☁ Облачность: {weather.clouds}%\n"
        f"🌧 Осадки за час: {_number(precipitation)} мм\n"
        f"🌅 Рассвет: {sunrise}\n"
        f"🌇 Закат: {sunset}\n"
        f"☀ Световой день: {daylight}\n"
        f"🍃 Качество воздуха: {air_text}"
    )


def format_comparison(left: CurrentWeather, right: CurrentWeather) -> str:
    left_name = left.location.name
    right_name = right.location.name
    rows = [
        ("🌡", "Температура", _temp(left.temperature), _temp(right.temperature)),
        ("🤍", "Ощущается", _temp(left.feels_like), _temp(right.feels_like)),
        ("💧", "Влажность", f"{left.humidity}%", f"{right.humidity}%"),
        (
            "🧭",
            "Давление",
            f"{round(left.pressure * .750062)} мм",
            f"{round(right.pressure * .750062)} мм",
        ),
        (
            "💨",
            "Ветер",
            f"{_number(left.wind_speed)} м/с",
            f"{_number(right.wind_speed)} м/с",
        ),
        ("☁", "Облачность", f"{left.clouds}%", f"{right.clouds}%"),
    ]
    lines = [
        "⚖ СРАВНЕНИЕ ПОГОДЫ",
        "",
        f"🔵 {left_name}",
        "🆚",
        f"🟢 {right_name}",
        "",
        "━━━━━━━━━━━━━━",
    ]
    for icon, name, left_value, right_value in rows:
        lines.extend(
            (
                "",
                f"{icon} {name}",
                f"🔵 {left_name}: {left_value}",
                f"🟢 {right_name}: {right_value}",
            )
        )

    difference = left.temperature - right.temperature
    if abs(difference) < 0.5:
        result = "Температура почти одинаковая."
    else:
        warmer = left.location.name if difference > 0 else right.location.name
        result = f"В городе {warmer} теплее на {abs(difference):.1f}°C."
    lines.extend(("", "━━━━━━━━━━━━━━", "", f"💡 {result}"))
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _DailySummary:
    day: date
    condition_id: int
    description: str
    minimum: float
    maximum: float
    humidity: int
    wind_speed: float
    pop: float
    precipitation: float


def _summarize_days(forecast: Forecast) -> list[_DailySummary]:
    groups: dict[date, list[ForecastPoint]] = defaultdict(list)
    for point in forecast.points:
        local_day = _local_datetime(point.timestamp, forecast.timezone_offset).date()
        groups[local_day].append(point)

    summaries = []
    for day, points in list(sorted(groups.items()))[:5]:
        popular_description = Counter(p.description for p in points).most_common(1)[0][0]
        representative = min(
            (p for p in points if p.description == popular_description),
            key=lambda p: abs(_local_datetime(p.timestamp, forecast.timezone_offset).hour - 12),
        )
        summaries.append(
            _DailySummary(
                day=day,
                condition_id=representative.condition_id,
                description=popular_description,
                minimum=min(p.temp_min for p in points),
                maximum=max(p.temp_max for p in points),
                humidity=round(sum(p.humidity for p in points) / len(points)),
                wind_speed=max(p.wind_speed for p in points),
                pop=max(p.precipitation_probability for p in points),
                precipitation=sum(p.rain_3h + p.snow_3h for p in points),
            )
        )
    return summaries


def _local_datetime(timestamp: int, offset: int) -> datetime:
    safe_offset = max(-86_399, min(86_399, offset))
    return datetime.fromtimestamp(timestamp, timezone(timedelta(seconds=safe_offset)))


def _format_time(timestamp: int | None, offset: int) -> str:
    return "нет данных" if timestamp is None else f"{_local_datetime(timestamp, offset):%H:%M}"


def _daylight(sunrise: int | None, sunset: int | None) -> str:
    if sunrise is None or sunset is None or sunset < sunrise:
        return "нет данных"
    minutes = (sunset - sunrise) // 60
    return f"{minutes // 60} ч {minutes % 60} мин"


def _dew_point(temperature: float, humidity: int) -> float | None:
    if humidity <= 0:
        return None
    alpha = math.log(humidity / 100) + (17.62 * temperature) / (243.12 + temperature)
    return 243.12 * alpha / (17.62 - alpha)


def _wind_direction(degrees: int | None) -> str:
    if degrees is None:
        return "направление неизвестно"
    names = (
        "северный",
        "северо-восточный",
        "восточный",
        "юго-восточный",
        "южный",
        "юго-западный",
        "западный",
        "северо-западный",
    )
    return names[round((degrees % 360) / 45) % 8]


def _temp(value: float) -> str:
    rounded = round(value)
    return f"{rounded:+d}°C"


def _number(value: float) -> str:
    return f"{value:.1f}".replace(".0", "")
