"""
Инициализация подключения к PostgreSQL и создание таблиц.
Используем asyncpg для асинхронной работы с БД.
"""

import asyncpg
import logging

from bot.config import config

logger = logging.getLogger(__name__)

# Глобальная ссылка на пул соединений
_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    """Создаёт пул соединений и сохраняет его в глобальную переменную."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=2,
        max_size=10,
    )
    logger.info("Пул соединений PostgreSQL создан")
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Возвращает существующий пул или создаёт новый."""
    global _pool
    if _pool is None:
        _pool = await create_pool()
    return _pool


async def close_pool() -> None:
    """Закрывает пул соединений."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Пул соединений PostgreSQL закрыт")


# ── SQL: создание таблиц ────────────────────────────────────
INIT_SQL = """
-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    id_tg       BIGINT UNIQUE,
    id_vk       BIGINT UNIQUE,
    id_max      BIGINT UNIQUE,
    name        VARCHAR(255),
    surname     VARCHAR(255)
);

-- Таблица дневника (5 вопросов за день + Readiness Score)
CREATE TABLE IF NOT EXISTS diary (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    data            JSONB NOT NULL DEFAULT '{}'::jsonb,
    readiness_score NUMERIC(4,1),
    UNIQUE(user_id, date)
);

-- Таблица событий / планировщик
CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_date  DATE NOT NULL,
    time        TIME NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    priority    INTEGER DEFAULT 5,
    event_type  VARCHAR(50) DEFAULT 'routine'
);

-- Таблица прогнозов DeepSeek
CREATE TABLE IF NOT EXISTS predictions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT NOW(),
    report      TEXT NOT NULL,
    feedback    JSONB
);
"""

# ── SQL: миграции (добавление колонок, если таблицы уже существуют) ──
MIGRATION_SQL = """
-- Добавляем event_type в events, если колонки нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'events' AND column_name = 'event_type'
    ) THEN
        ALTER TABLE events ADD COLUMN event_type VARCHAR(50) DEFAULT 'routine';
    END IF;
END $$;

-- Добавляем readiness_score в diary, если колонки нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'diary' AND column_name = 'readiness_score'
    ) THEN
        ALTER TABLE diary ADD COLUMN readiness_score NUMERIC(4,1);
    END IF;
END $$;
"""


async def init_db(pool: asyncpg.Pool) -> None:
    """Выполняет SQL инициализации таблиц и миграций."""
    async with pool.acquire() as conn:
        await conn.execute(INIT_SQL)
        await conn.execute(MIGRATION_SQL)
    logger.info("Таблицы БД проверены / созданы, миграции применены")
