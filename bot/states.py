"""
FSM-состояния бота.
Каждая группа соответствует отдельному сценарию взаимодействия.
"""

from aiogram.fsm.state import State, StatesGroup


# ── Главное меню ─────────────────────────────────────────────
class MainMenu(StatesGroup):
    """Ожидание выбора в главном меню."""
    waiting_action = State()


# ── Настройки ────────────────────────────────────────────────
class Settings(StatesGroup):
    """Смена имени пользователя."""
    waiting_new_name = State()


# ── Записать день (вечерний чекин) ──────────────────────────
class Diary(StatesGroup):
    """Полный цикл записи / редактирования дня."""

    # Выбор даты
    waiting_date = State()

    # 5-вопросный чекин
    waiting_score = State()
    waiting_comment = State()

    # Действия с существующей записью
    waiting_existing_action = State()

    # Изменение конкретного вопроса (оценка / комментарий)
    waiting_edit_question = State()
    waiting_edit_score = State()
    waiting_edit_comment = State()

    # Добавление к существующей записи
    waiting_add_question = State()
    waiting_add_score = State()
    waiting_add_comment = State()

    # Подтверждение удаления
    waiting_delete_confirm = State()


# ── Запланировать (календарь событий) ───────────────────────
class Planner(StatesGroup):
    """Управление событиями."""

    # Выбор действия (добавить / изменить / удалить)
    waiting_action = State()

    # Выбор даты
    waiting_date = State()

    # Добавление события — 4 шага
    waiting_time = State()
    waiting_name = State()
    waiting_description = State()
    waiting_priority = State()

    # Выбор события из списка (изменить / удалить)
    waiting_event_choice = State()

    # Подтверждение удаления
    waiting_delete_confirm = State()

    # Изменение события — выбор поля
    waiting_edit_field = State()
    waiting_edit_value = State()

    # Пагинация
    waiting_page = State()


# ── Циклы (DeepSeek) ────────────────────────────────────────
class Cycles(StatesGroup):
    """Работа с прогнозами DeepSeek."""

    waiting_action = State()

    # Оценка расчёта
    waiting_feedback_date = State()
    waiting_feedback_applied = State()
    waiting_feedback_result = State()
