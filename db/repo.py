"""
CRUD-операции (Repository) для работы с таблицами БД.
Все методы асинхронные, используют пул соединений asyncpg.
"""

import asyncpg
import json
from datetime import date, time as dtime
from typing import Optional


class Repo:
    """Репозиторий для доступа к данным PostgreSQL."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ── Пользователи ─────────────────────────────────────────

    async def get_user_by_tg(self, id_tg: int) -> Optional[asyncpg.Record]:
        """Возвращает пользователя по Telegram ID."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE id_tg = $1", id_tg
            )

    async def create_user(
        self,
        id_tg: Optional[int] = None,
        id_vk: Optional[int] = None,
        id_max: Optional[int] = None,
        name: str = "",
        surname: str = "",
    ) -> asyncpg.Record:
        """Создаёт нового пользователя и возвращает его запись."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO users (id_tg, id_vk, id_max, name, surname)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                id_tg,
                id_vk,
                id_max,
                name,
                surname,
            )

    async def update_user_name(self, user_id: int, new_name: str) -> None:
        """Обновляет имя пользователя."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET name = $1 WHERE id = $2",
                new_name,
                user_id,
            )

    # ── Дневник ──────────────────────────────────────────────

    async def get_diary_entry(self, user_id: int, entry_date: date) -> Optional[asyncpg.Record]:
        """Возвращает запись дневника за указанную дату."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM diary WHERE user_id = $1 AND date = $2",
                user_id,
                entry_date,
            )

    async def create_diary_entry(self, user_id: int, entry_date: date, data: dict) -> asyncpg.Record:
        """Создаёт новую запись дневника."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO diary (user_id, date, data)
                VALUES ($1, $2, $3::jsonb)
                RETURNING *
                """,
                user_id,
                entry_date,
                json.dumps(data),
            )

    async def update_diary_entry(self, user_id: int, entry_date: date, data: dict) -> None:
        """Полностью обновляет JSON-данные записи дневника."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE diary SET data = $1::jsonb WHERE user_id = $2 AND date = $3",
                json.dumps(data),
                user_id,
                entry_date,
            )

    async def delete_diary_entry(self, user_id: int, entry_date: date) -> None:
        """Удаляет запись дневника за указанную дату."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM diary WHERE user_id = $1 AND date = $2",
                user_id,
                entry_date,
            )

    # ── События ──────────────────────────────────────────────

    async def create_event(
        self,
        user_id: int,
        event_date: date,
        event_time: dtime,
        name: str,
        description: str,
        priority: int,
    ) -> asyncpg.Record:
        """Создаёт новое событие."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO events (user_id, event_date, time, name, description, priority)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                user_id,
                event_date,
                event_time,
                name,
                description,
                priority,
            )

    async def get_events_by_date(self, user_id: int, event_date: date) -> list[asyncpg.Record]:
        """Возвращает список событий на указанную дату."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT * FROM events
                WHERE user_id = $1 AND event_date = $2
                ORDER BY time ASC
                """,
                user_id,
                event_date,
            )

    async def get_event_by_id(self, event_id: int) -> Optional[asyncpg.Record]:
        """Возвращает событие по его ID."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM events WHERE id = $1", event_id
            )

    async def update_event_field(self, event_id: int, field: str, value) -> None:
        """
        Обновляет одно поле события.
        Внимание: field передаётся как имя колонки — используется только
        из доверенного кода (не от пользователя напрямую).
        """
        allowed_fields = {"event_date", "time", "name", "description", "priority"}
        if field not in allowed_fields:
            raise ValueError(f"Запрещённое поле для обновления: {field}")
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE events SET {field} = $1 WHERE id = $2",
                value,
                event_id,
            )

    async def delete_event(self, event_id: int) -> None:
        """Удаляет событие по ID."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM events WHERE id = $1", event_id
            )

    # ── Прогнозы (DeepSeek) ─────────────────────────────────

    async def create_prediction(self, user_id: int, report: str) -> asyncpg.Record:
        """Сохраняет прогноз DeepSeek."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO predictions (user_id, report)
                VALUES ($1, $2)
                RETURNING *
                """,
                user_id,
                report,
            )

    async def get_last_prediction(self, user_id: int) -> Optional[asyncpg.Record]:
        """Возвращает последний прогноз пользователя."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM predictions
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
            )

    async def update_prediction_feedback(self, prediction_id: int, feedback: dict) -> None:
        """Обновляет feedback прогноза."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE predictions SET feedback = $1::jsonb WHERE id = $2",
                json.dumps(feedback),
                prediction_id,
            )

    # ── Агрегация для DeepSeek ───────────────────────────────

    async def get_all_history_and_events(self, user_id: int) -> dict:
        """
        Достаёт все записи дневника и все будущие события
        для формирования промпта к DeepSeek.
        """
        async with self.pool.acquire() as conn:
            diary_rows = await conn.fetch(
                """
                SELECT date, data FROM diary
                WHERE user_id = $1
                ORDER BY date ASC
                """,
                user_id,
            )
            events_rows = await conn.fetch(
                """
                SELECT event_date, time, name, description, priority FROM events
                WHERE user_id = $1 AND event_date >= CURRENT_DATE
                ORDER BY event_date ASC, time ASC
                """,
                user_id,
            )

        diary_list = [
            {"date": str(r["date"]), "data": r["data"]} for r in diary_rows
        ]
        events_list = [
            {
                "date": str(r["event_date"]),
                "time": str(r["time"])[:5],
                "name": r["name"],
                "description": r["description"],
                "priority": r["priority"],
            }
            for r in events_rows
        ]

        return {"diary": diary_list, "events": events_list}
