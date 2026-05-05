"""
Интеграция с DeepSeek API через openai-клиент.
"""

import logging
from openai import AsyncOpenAI

from bot.config import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — эксперт по биохакингу. Проанализируй историю дневника и календарь событий. "
    "Прогнозируй состояние пользователя на 10 дней вперед. "
    "Для каждого дня с событием укажи: Прогноз энергии/стресса и конкретную рекомендацию "
    "по подготовке (сон, спорт, питание). Учитывай приоритет событий. "
    "Формат: ДД.ММ - Событие - Прогноз - Рекомендация."
)


class DeepSeekService:
    """Сервис для работы с DeepSeek API."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.DS_API_KEY,
            base_url=config.DS_BASE_URL,
        )

    async def predict(self, user_prompt: str) -> str:
        """
        Отправляет запрос к DeepSeek и возвращает текстовый прогноз.

        :param user_prompt: Сформированный промпт с историей пользователя.
        :return: Текстовый ответ модели.
        """
        try:
            response = await self.client.chat.completions.create(
                model=config.DS_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            result = response.choices[0].message.content
            logger.info("Получен ответ от DeepSeek (длина=%d)", len(result))
            return result
        except Exception as e:
            logger.error("Ошибка при запросе к DeepSeek: %s", e)
            raise


# Глобальный экземпляр сервиса
deepseek_service = DeepSeekService()
