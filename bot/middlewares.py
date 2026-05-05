"""
Middleware: проверка / автоматическая регистрация пользователя в БД.
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from db.repo import Repo


class RegisterMiddleware(BaseMiddleware):
    """
    При каждом сообщении проверяем, есть ли пользователь в БД.
    Если нет — автоматически создаём запись.
    """

    async def __call__(self, handler, event: Message | CallbackQuery, data: dict):
        repo: Repo = data.get("repo")
        if repo is None:
            return await handler(event, data)

        user = event.from_user
        if user is None:
            return await handler(event, data)

        # Проверяем наличие пользователя по Telegram ID
        db_user = await repo.get_user_by_tg(user.id)
        if db_user is None:
            await repo.create_user(
                id_tg=user.id,
                name=user.first_name or "",
                surname=user.last_name or "",
            )

        return await handler(event, data)
