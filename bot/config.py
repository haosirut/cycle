"""
Конфигурация приложения.
Чтение переменных окружения с помощью python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Центральный конфиг: все настройки из .env / окружения."""

    # ── Telegram Bot ──────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # ── DeepSeek API ──────────────────────────────────────────
    DS_API_KEY: str = os.getenv("DS_API_KEY", "")
    DS_BASE_URL: str = "https://api.deepseek.com"
    DS_MODEL: str = "deepseek-chat"

    # ── PostgreSQL (Amvera internal) ──────────────────────────
    DB_HOST: str = os.getenv("DB_HOST", "db")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "cycle_db")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "")

    # ── DSN для asyncpg ───────────────────────────────────────
    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


config = Config()
