"""Потокобезопасное временное хранилище состояния диалогов."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Protocol

from weather_bot.models import Location


class Action(str, Enum):
    CURRENT = "current"
    FORECAST = "forecast"
    SET_CITY = "set_city"
    LOCATION = "location"
    ADVANCED = "advanced"
    COMPARE = "compare"
    REPORT_ERROR = "report_error"


@dataclass(slots=True)
class UserState:
    home_city: Location | None = None
    pending: Action | None = None


class UserStore(Protocol):
    def get(self, user_id: int) -> UserState: ...

    def set_pending(self, user_id: int, action: Action | None) -> None: ...

    def set_home_city(self, user_id: int, location: Location) -> None: ...

    def clear_home_city(self, user_id: int) -> None: ...


class FeedbackStore(Protocol):
    def create(self, user_id: int, peer_id: int, text: str) -> int: ...


class MemoryUserStore:
    """Хранит настройки только до остановки процесса, без базы данных."""

    def __init__(self) -> None:
        self._states: dict[int, UserState] = {}
        self._lock = RLock()

    def get(self, user_id: int) -> UserState:
        with self._lock:
            state = self._states.setdefault(user_id, UserState())
            return UserState(state.home_city, state.pending)

    def set_pending(self, user_id: int, action: Action | None) -> None:
        with self._lock:
            self._states.setdefault(user_id, UserState()).pending = action

    def set_home_city(self, user_id: int, location: Location) -> None:
        with self._lock:
            state = self._states.setdefault(user_id, UserState())
            state.home_city = location
            state.pending = None

    def clear_home_city(self, user_id: int) -> None:
        with self._lock:
            state = self._states.setdefault(user_id, UserState())
            state.home_city = None
            state.pending = None


class MemoryFeedbackStore:
    """Тестовая реализация; в рабочем приложении используется SQLite."""

    def __init__(self) -> None:
        self.items: list[tuple[int, int, str]] = []

    def create(self, user_id: int, peer_id: int, text: str) -> int:
        self.items.append((user_id, peer_id, text))
        return len(self.items)
