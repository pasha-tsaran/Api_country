"""Типы предметной области, независимые от VK и HTTP."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Location:
    name: str
    country: str
    latitude: float
    longitude: float
    state: str | None = None

    @property
    def title(self) -> str:
        details = [self.name]
        if self.state and self.state.casefold() != self.name.casefold():
            details.append(self.state)
        if self.country:
            details.append(self.country)
        return ", ".join(details)


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    location: Location
    measured_at: int
    timezone_offset: int
    condition_id: int
    description: str
    temperature: float
    feels_like: float
    temp_min: float
    temp_max: float
    pressure: int
    humidity: int
    visibility: int | None
    wind_speed: float
    wind_degrees: int | None
    wind_gust: float | None
    clouds: int
    rain_1h: float
    snow_1h: float
    sunrise: int | None
    sunset: int | None


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    timestamp: int
    condition_id: int
    description: str
    temperature: float
    temp_min: float
    temp_max: float
    feels_like: float
    humidity: int
    wind_speed: float
    precipitation_probability: float
    rain_3h: float
    snow_3h: float


@dataclass(frozen=True, slots=True)
class Forecast:
    location: Location
    timezone_offset: int
    points: tuple[ForecastPoint, ...]


@dataclass(frozen=True, slots=True)
class AirQuality:
    index: int
    pm2_5: float | None
    pm10: float | None
