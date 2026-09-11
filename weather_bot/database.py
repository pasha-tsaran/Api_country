"""SQLite-хранилище пользователей, диалогов, обращений и логов."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from weather_bot.models import Location
from weather_bot.storage import Action, UserState

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    vk_user_id INTEGER PRIMARY KEY,
    pending_action TEXT,
    home_name TEXT,
    home_state TEXT,
    home_country TEXT,
    home_latitude REAL,
    home_longitude REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dialog_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vk_user_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_dialog_user ON dialog_messages(vk_user_id);
CREATE INDEX IF NOT EXISTS ix_dialog_created ON dialog_messages(created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vk_user_id INTEGER NOT NULL,
    source_peer_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_feedback_user ON feedback(vk_user_id);
CREATE INDEX IF NOT EXISTS ix_feedback_status ON feedback(status);

CREATE TABLE IF NOT EXISTS application_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    logger TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_logs_level ON application_logs(level);
CREATE INDEX IF NOT EXISTS ix_logs_created ON application_logs(created_at);
"""


@dataclass(frozen=True, slots=True)
class DialogMessage:
    id: int
    vk_user_id: int
    peer_id: int
    direction: str
    text: str
    details: dict[str, Any] | None
    created_at: str


class Database:
    """Создаёт короткоживущие соединения, безопасные для разных потоков."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)

    def close(self) -> None:
        """Соединения закрываются после каждой операции; метод сохраняет API сборки."""


class SqliteUserStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, user_id: int) -> UserState:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE vk_user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return UserState()

        location = None
        if (
            row["home_name"] is not None
            and row["home_latitude"] is not None
            and row["home_longitude"] is not None
        ):
            location = Location(
                name=row["home_name"],
                state=row["home_state"],
                country=row["home_country"] or "",
                latitude=row["home_latitude"],
                longitude=row["home_longitude"],
            )
        return UserState(location, _parse_action(row["pending_action"]))

    def set_pending(self, user_id: int, action: Action | None) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users(vk_user_id, pending_action)
                VALUES (?, ?)
                ON CONFLICT(vk_user_id) DO UPDATE SET
                    pending_action = excluded.pending_action,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, action.value if action else None),
            )

    def set_home_city(self, user_id: int, location: Location) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users(
                    vk_user_id, home_name, home_state, home_country,
                    home_latitude, home_longitude, pending_action
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(vk_user_id) DO UPDATE SET
                    home_name = excluded.home_name,
                    home_state = excluded.home_state,
                    home_country = excluded.home_country,
                    home_latitude = excluded.home_latitude,
                    home_longitude = excluded.home_longitude,
                    pending_action = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    location.name,
                    location.state,
                    location.country,
                    location.latitude,
                    location.longitude,
                ),
            )

    def clear_home_city(self, user_id: int) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users(vk_user_id)
                VALUES (?)
                ON CONFLICT(vk_user_id) DO UPDATE SET
                    home_name = NULL,
                    home_state = NULL,
                    home_country = NULL,
                    home_latitude = NULL,
                    home_longitude = NULL,
                    pending_action = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id,),
            )


class SqliteFeedbackStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, user_id: int, peer_id: int, text: str) -> int:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO feedback(vk_user_id, source_peer_id, text)
                VALUES (?, ?, ?)
                """,
                (user_id, peer_id, text),
            )
            feedback_id = cursor.lastrowid
        if feedback_id is None:
            raise sqlite3.DatabaseError("SQLite не вернул ID обращения")
        return feedback_id


class DialogHistoryStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def record(
        self,
        *,
        user_id: int,
        peer_id: int,
        direction: str,
        text: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO dialog_messages(
                    vk_user_id, peer_id, direction, text, details
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, peer_id, direction, text, _to_json(details)),
            )

    def recent(self, user_id: int, limit: int = 50) -> list[DialogMessage]:
        safe_limit = max(1, min(limit, 500))
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, vk_user_id, peer_id, direction, text, details, created_at
                FROM dialog_messages
                WHERE vk_user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, safe_limit),
            ).fetchall()
        return [
            DialogMessage(
                id=row["id"],
                vk_user_id=row["vk_user_id"],
                peer_id=row["peer_id"],
                direction=row["direction"],
                text=row["text"],
                details=json.loads(row["details"]) if row["details"] else None,
                created_at=row["created_at"],
            )
            for row in rows
        ]


class DatabaseLogHandler(logging.Handler):
    """Сохраняет прикладные логи, не прерывая бота при ошибке записи."""

    def __init__(self, database: Database) -> None:
        super().__init__(level=logging.INFO)
        self._database = database

    def emit(self, record: logging.LogRecord) -> None:
        try:
            details: dict[str, Any] = {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            if record.exc_info:
                details["exception"] = logging.Formatter().formatException(record.exc_info)
            with self._database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO application_logs(level, logger, message, details)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        record.levelname,
                        record.name,
                        record.getMessage(),
                        _to_json(details),
                    ),
                )
        except Exception:
            self.handleError(record)


def _parse_action(value: str | None) -> Action | None:
    try:
        return Action(value) if value else None
    except ValueError:
        return None


def _to_json(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None
