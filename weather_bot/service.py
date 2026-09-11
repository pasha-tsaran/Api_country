"""Сценарии получения данных и небольшой TTL-кеш запросов."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Callable, Generic, TypeVar

from weather_bot.models import AirQuality, CurrentWeather, Forecast, Location
from weather_bot.openweather import OpenWeatherClient, WeatherError

T = TypeVar("T")


@dataclass(slots=True)
class _CacheItem(Generic[T]):
    expires_at: float
    value: T


class WeatherService:
    """Предоставляет боту погодные операции без деталей HTTP API."""

    def __init__(
        self,
        client: OpenWeatherClient,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._client = client
        self._clock = clock
        self._cache: dict[tuple[str, object], _CacheItem[object]] = {}
        self._lock = RLock()

    def resolve_city(self, city: str) -> Location:
        normalized = " ".join(city.split()).casefold()
        return self._cached(
            ("city", normalized), 6 * 60 * 60, lambda: self._client.find_location(city)
        )

    def resolve_coordinates(self, latitude: float, longitude: float) -> Location:
        key = (round(latitude, 3), round(longitude, 3))
        return self._cached(
            ("coordinates", key),
            6 * 60 * 60,
            lambda: self._client.reverse_location(latitude, longitude),
        )

    def current(self, location: Location) -> CurrentWeather:
        return self._cached(
            ("current", self._location_key(location)),
            10 * 60,
            lambda: self._client.current(location),
        )

    def forecast(self, location: Location) -> Forecast:
        return self._cached(
            ("forecast", self._location_key(location)),
            30 * 60,
            lambda: self._client.forecast(location),
        )

    def air_quality(self, location: Location) -> AirQuality | None:
        try:
            return self._cached(
                ("air", self._location_key(location)),
                20 * 60,
                lambda: self._client.air_quality(location),
            )
        except WeatherError:
            # Погода остаётся полезной, даже если отдельный API воздуха недоступен.
            return None

    def _cached(self, key: tuple[str, object], ttl: float, load: Callable[[], T]) -> T:
        now = self._clock()
        with self._lock:
            item = self._cache.get(key)
            if item and item.expires_at > now:
                return item.value  # type: ignore[return-value]

        value = load()
        with self._lock:
            self._cache[key] = _CacheItem(now + ttl, value)
        return value

    @staticmethod
    def _location_key(location: Location) -> tuple[float, float]:
        return round(location.latitude, 3), round(location.longitude, 3)
