"""
Клавиатуры (Reply и Inline) для всех сценариев бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ── Главное меню ─────────────────────────────────────────────
def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню бота с 4 основными разделами."""
    kb = [
        [KeyboardButton(text="Настройки"), KeyboardButton(text="Записать день")],
        [KeyboardButton(text="Запланировать"), KeyboardButton(text="Циклы")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ── Настройки ────────────────────────────────────────────────
def settings_kb() -> ReplyKeyboardMarkup:
    """Подменю настроек."""
    kb = [[KeyboardButton(text="Изменить Имя")], [KeyboardButton(text="🔙 Назад")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ── Оценка 1-10 ─────────────────────────────────────────────
def score_kb(prefix: str = "score") -> InlineKeyboardMarkup:
    """Инлайн-клавиатура с оценками от 1 до 10 (2 ряда по 5)."""
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:1:{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:1:{i}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


# ── Действия с существующей записью дня ─────────────────────
def existing_entry_kb() -> InlineKeyboardMarkup:
    """Меню действий, если запись за день уже существует."""
    kb = [
        [
            InlineKeyboardButton(text="Перезаписать", callback_data="diary:rewrite"),
            InlineKeyboardButton(text="Изменить", callback_data="diary:edit"),
        ],
        [
            InlineKeyboardButton(text="Добавить", callback_data="diary:add"),
            InlineKeyboardButton(text="Удалить", callback_data="diary:delete"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Клавиатура редактирования вопросов (1-5 / О-О...) ───────
def edit_questions_kb(data: dict, prefix: str = "editq") -> InlineKeyboardMarkup:
    """
    Клавиатура для изменения оценок и комментариев к 5 вопросам.
    Верхний ряд — цифры (изменить оценку), нижний — «О» (изменить комментарий).
    """
    row_nums = []
    row_comments = []
    for i in range(1, 6):
        q = data.get(f"q{i}", {})
        score_val = q.get("score", "—")
        row_nums.append(
            InlineKeyboardButton(
                text=f"[{i}] {score_val}",
                callback_data=f"{prefix}:score:{i}",
            )
        )
        row_comments.append(
            InlineKeyboardButton(
                text=f"О{i}",
                callback_data=f"{prefix}:comment:{i}",
            )
        )
    back_row = [InlineKeyboardButton(text="🔙 Готово", callback_data=f"{prefix}:done")]
    return InlineKeyboardMarkup(inline_keyboard=[row_nums, row_comments, back_row])


# ── Клавиатура добавления к вопросам ────────────────────────
def add_questions_kb(data: dict, prefix: str = "addq") -> InlineKeyboardMarkup:
    """Клавиатура для добавления оценок и комментариев к 5 вопросам."""
    row_nums = []
    row_comments = []
    for i in range(1, 6):
        q = data.get(f"q{i}", {})
        score_val = q.get("score", "—")
        row_nums.append(
            InlineKeyboardButton(
                text=f"[{i}] {score_val}",
                callback_data=f"{prefix}:score:{i}",
            )
        )
        row_comments.append(
            InlineKeyboardButton(
                text=f"О{i}",
                callback_data=f"{prefix}:comment:{i}",
            )
        )
    back_row = [InlineKeyboardButton(text="🔙 Готово", callback_data=f"{prefix}:done")]
    return InlineKeyboardMarkup(inline_keyboard=[row_nums, row_comments, back_row])


# ── Планировщик: выбор действия ─────────────────────────────
def planner_action_kb() -> InlineKeyboardMarkup:
    """Меню: Добавить / Изменить / Удалить событие."""
    kb = [
        [
            InlineKeyboardButton(text="Добавить", callback_data="plan:add"),
            InlineKeyboardButton(text="Изменить", callback_data="plan:edit"),
        ],
        [InlineKeyboardButton(text="Удалить", callback_data="plan:delete")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Список событий с пагинацией ─────────────────────────────
def events_list_kb(
    events: list,
    page: int = 0,
    per_page: int = 9,
    prefix: str = "pevt",
) -> InlineKeyboardMarkup:
    """
    Показывает до 9 событий на странице.
    Если событий > 9, добавляется кнопка «Далее».
    """
    start = page * per_page
    end = start + per_page
    page_events = events[start:end]

    rows = []
    for idx, ev in enumerate(page_events, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{idx}. [{ev['time'][:5]}] {ev['name']}",
                    callback_data=f"{prefix}:pick:{ev['id']}",
                )
            ]
        )

    # Пагинация
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}:page:{page - 1}")
        )
    if end < len(events):
        nav_row.append(
            InlineKeyboardButton(text="Далее ▶️", callback_data=f"{prefix}:page:{page + 1}")
        )
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Выбор поля для редактирования события ───────────────────
def event_edit_field_kb() -> InlineKeyboardMarkup:
    """Меню выбора поля события для редактирования."""
    kb = [
        [
            InlineKeyboardButton(text="Дата", callback_data="efield:event_date"),
            InlineKeyboardButton(text="Время", callback_data="efield:time"),
        ],
        [
            InlineKeyboardButton(text="Название", callback_data="efield:name"),
            InlineKeyboardButton(text="Описание", callback_data="efield:description"),
        ],
        [InlineKeyboardButton(text="Приоритет", callback_data="efield:priority")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Подтверждение Да/Нет ────────────────────────────────────
def confirm_kb(prefix: str = "confirm") -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    kb = [
        [
            InlineKeyboardButton(text="Да", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton(text="Нет", callback_data=f"{prefix}:no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Циклы: меню действий ────────────────────────────────────
def cycles_menu_kb() -> InlineKeyboardMarkup:
    """Меню раздела «Циклы»."""
    kb = [
        [InlineKeyboardButton(text="Рассчитать на 10 дней", callback_data="cycle:calc")],
        [InlineKeyboardButton(text="Показать последний расчёт", callback_data="cycle:last")],
        [InlineKeyboardButton(text="Оценить расчёт", callback_data="cycle:feedback")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Оценка прогноза: Да/Нет ────────────────────────────────
def feedback_applied_kb() -> InlineKeyboardMarkup:
    """Применил ли пользователь рекомендацию?"""
    kb = [
        [
            InlineKeyboardButton(text="Да", callback_data="fb:applied:yes"),
            InlineKeyboardButton(text="Нет", callback_data="fb:applied:no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Клавиатура «Назад» в главное меню ──────────────────────
def back_to_main_kb() -> ReplyKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    kb = [[KeyboardButton(text="🔙 Назад")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
