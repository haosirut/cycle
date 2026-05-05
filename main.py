"""
Точка входа: инициализация диспетчера, подключение роутеров, запуск polling.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import config
from bot.handlers import router as main_router
from bot.middlewares import RegisterMiddleware
from db.database import create_pool, init_db, close_pool
from db.repo import Repo

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # ── Проверка обязательных переменных ────────────────────
    if not config.BOT_TOKEN:
        logger.critical("BOT_TOKEN не задан! Установите переменную окружения.")
        sys.exit(1)

    # ── Инициализация БД ────────────────────────────────────
    pool = await create_pool()
    await init_db(pool)
    repo = Repo(pool)
    logger.info("База данных инициализирована")

    # ── Инициализация бота и диспетчера ─────────────────────
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # Сохраняем repo в bot-объект для доступа из хэндлеров
    bot["repo"] = repo

    dp = Dispatcher()

    # Подключаем middleware
    dp.message.middleware(RegisterMiddleware())
    dp.callback_query.middleware(RegisterMiddleware())

    # Подключаем роутер с хэндлерами
    dp.include_router(main_router)

    # ── Запуск polling ──────────────────────────────────────
    logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
