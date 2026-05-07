"""
Роутеры и хэндлеры команд Telegram-бота.
Вся бизнес-логика взаимодействия с пользователем.
"""

import json
import logging
from datetime import date, time as dtime, datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from bot.keyboards import (
    main_menu_kb,
    settings_kb,
    score_kb,
    existing_entry_kb,
    edit_questions_kb,
    add_questions_kb,
    planner_action_kb,
    events_list_kb,
    event_edit_field_kb,
    event_type_kb,
    EVENT_TYPES,
    confirm_kb,
    cycles_menu_kb,
    feedback_applied_kb,
    back_to_main_kb,
)
from bot.states import (
    Settings,
    Diary,
    Planner,
    Cycles,
)
from db.repo import Repo
from services.deepseek_service import deepseek_service

router = Router()
logger = logging.getLogger(__name__)

# ── Константы вопросов чекина ───────────────────────────────
# Формат: (короткое_название, полный_текст_вопроса, подвопрос)
QUESTIONS = [
    (
        "Энергия",
        "Какой был уровень энергии в течение дня? Насколько хватало физических сил "
        "на всё, что ты делал? Оцени не момент прямо сейчас, а общее ощущение "
        "«заряженности» за день — от подъёма до вечера.\n"
        "1 — еле дотянул, 10 — полный резервуар.",
        "Что повлияло на уровень энергии за день?",
    ),
    (
        "Ясность",
        "Насколько ясным был ум в течение дня? Легко ли соображалось, принимались "
        "решения, удерживалась мысль? Оцени качество работы головы за весь день.\n"
        "1 — постоянный туман и путаница, 10 — кристальная ясность мышления.",
        "Что повлияло на ясность мышления за день?",
    ),
    (
        "Вовлечённость",
        "Насколько ты был включён в происходящее в течение дня? Чувствовал ли себя "
        "автором своих действий, или скорее тянулся по инерции? Было ли желание "
        "влиять на события, брать на себя, действовать от себя?\n"
        "1 — полное отсутствие воли, всё равно, 10 — максимально включён, управляю ситуацией.",
        "Что повлияло на включённость и мотивацию за день?",
    ),
    (
        "Напряжение",
        "Какой была нагрузка на тебя в течение дня? Сколько давления — внешних "
        "требований, дедлайнов, конфликтов, внутренней тревоги — ты нёс? Оцени "
        "не стресс как эмоцию, а общий груз на плечах.\n"
        "1 — никакой нагрузки, полная расслабленность, 10 — на пределе, всё давит.",
        "Что повлияло на уровень напряжения за день?",
    ),
    (
        "Восстановление",
        "Насколько качественно ты восстановился за прошедшую ночь и день? "
        "Почувствовал ли подзарядку от сна, были ли моменты отдыха, или с утра "
        "уже не выспался? Оцени именно качество регенерации, а не количество часов.\n"
        "1 — совершенно не восстановился, организм не перезагрузился, "
        "10 — полностью регенерирован, чувствую себя обновлённым.",
        "Что повлияло на качество восстановления?",
    ),
]

# ── Веса для Readiness Score ────────────────────────────────
# q1=Энергия(0.25), q2=Ясность(0.20), q3=Вовлечённость(0.15),
# q4=Напряжение(0.10 инвертированное), q5=Восстановление(0.30)
READINESS_WEIGHTS = {
    "q1": 0.25,  # Энергия
    "q2": 0.20,  # Ясность
    "q3": 0.15,  # Вовлечённость
    "q4": 0.10,  # Напряжение (инвертируется)
    "q5": 0.30,  # Восстановление
}


# ── Вспомогательные функции ─────────────────────────────────

async def _ensure_state_data(state: FSMContext) -> dict:
    """Возвращает данные FSM или пустой словарь."""
    data = await state.get_data()
    return data if data else {}


def _parse_date(text: str) -> date | None:
    """Парсит дату из текста (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(text: str) -> dtime | None:
    """Парсит время из текста (ЧЧ:ММ)."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt).time()
        except ValueError:
            continue
    return None


def _split_long_message(text: str, max_len: int = 4000) -> list[str]:
    """Разбивает длинный текст на части для отправки в Telegram."""
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


def _calc_readiness_score(diary_data: dict) -> float:
    """
    Вычисляет Readiness Score по формуле:
    Readiness = Восстановление×0.30 + Энергия×0.25 + Ясность×0.20
              + Вовлечённость×0.15 + (10−Напряжение)×0.10
    """
    score = 0.0
    for q_key, weight in READINESS_WEIGHTS.items():
        q_info = diary_data.get(q_key, {})
        val = q_info.get("score", 5)
        if q_key == "q4":
            # Напряжение — инвертируем (чем больше, тем хуже)
            val = 10 - val
        score += val * weight
    return round(score, 1)


def _readiness_emoji(score: float) -> str:
    """Возвращает эмодзи в зависимости от Readiness Score."""
    if score >= 8:
        return "🟢"
    elif score >= 6:
        return "🟡"
    elif score >= 4:
        return "🟠"
    else:
        return "🔴"


def _detect_trend(recent_entries: list) -> str:
    """
    Определяет тренд Readiness Score по последним записям.
    Возвращает: '📈 растёт', '📉 падает', '➡️ стабилен'.
    """
    if len(recent_entries) < 2:
        return "➡️ недостаточно данных"

    scores = []
    for entry in recent_entries:
        rs = entry.get("readiness_score")
        if rs is not None:
            scores.append(float(rs))
        else:
            # Вычисляем из data
            d = entry.get("data", {})
            if isinstance(d, str):
                d = json.loads(d)
            scores.append(_calc_readiness_score(d))

    if len(scores) < 2:
        return "➡️ недостаточно данных"

    # Смотрим последние 3 значения (или меньше)
    recent = scores[-3:]
    if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
        return "📈 растёт"
    elif all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
        return "📉 падает"
    else:
        return "➡️ стабилен"


def _build_diary_prompt(diary_data: dict, events_data: dict) -> str:
    """Формирует текстовый промпт для DeepSeek из данных пользователя."""
    parts = ["История дневника продуктивности (5 измерений):\n"]

    # Названия вопросов для расшифровки
    q_names = {f"q{i+1}": QUESTIONS[i][0] for i in range(5)}

    for entry in diary_data.get("diary", []):
        rs = entry.get("readiness_score")
        rs_text = f" | Readiness: {rs}" if rs else ""
        parts.append(f"  Дата: {entry['date']}{rs_text}")
        d = entry.get("data", {})
        if isinstance(d, str):
            d = json.loads(d)
        for qk, qv in d.items():
            name = q_names.get(qk, qk)
            parts.append(f"    {name}: оценка={qv.get('score')}, коммент={qv.get('comment')}")
        parts.append("")

    parts.append("\nПредстоящие события:\n")
    type_labels = {
        "presentation": "Выступление",
        "physical": "Физ. нагрузка",
        "strategic": "Стратег. решение",
        "routine": "Рутина",
        "negotiation": "Переговоры",
    }
    for ev in events_data.get("events", []):
        et = type_labels.get(ev.get("event_type", ""), ev.get("event_type", ""))
        parts.append(
            f"  {ev['date']} {ev['time']} — [{et}] {ev['name']} "
            f"(приоритет: {ev['priority']}): {ev['description']}"
        )

    return "\n".join(parts)


# ════════════════════════════════════════════════════════════
#  /start и Главное меню
# ════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в бот анализа циклов продуктивности!\n"
        "Выберите действие в меню ниже.",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "🔙 Назад")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_kb())


# ════════════════════════════════════════════════════════════
#  А. Настройки
# ════════════════════════════════════════════════════════════

@router.message(F.text == "Настройки")
async def menu_settings(message: Message, state: FSMContext):
    await state.set_state(Settings.waiting_new_name)
    await message.answer("⚙️ Раздел настроек", reply_markup=settings_kb())


@router.message(Settings.waiting_new_name, F.text == "Изменить Имя")
async def ask_new_name(message: Message, state: FSMContext):
    await state.set_state(Settings.waiting_new_name)
    await message.answer("Введите новое имя:")


@router.message(Settings.waiting_new_name)
async def save_new_name(message: Message, state: FSMContext):
    if message.text in ("🔙 Назад", "Изменить Имя", "Настройки",
                        "Записать день", "Запланировать", "Циклы"):
        await message.answer("Пожалуйста, введите новое имя текстом:")
        return
    repo: Repo = message.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(message.from_user.id)
    await repo.update_user_name(user["id"], message.text.strip())
    await message.answer(f"✅ Имя обновлено на: {message.text.strip()}")
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_kb())


# ════════════════════════════════════════════════════════════
#  Б. Записать день (Вечерний чекин)
# ════════════════════════════════════════════════════════════

@router.message(F.text == "Записать день")
async def diary_ask_date(message: Message, state: FSMContext):
    await state.set_state(Diary.waiting_date)
    await message.answer(
        "📅 Введите дату для записи (формат ДД.ММ.ГГГГ):",
        reply_markup=back_to_main_kb(),
    )


@router.message(Diary.waiting_date)
async def diary_process_date(message: Message, state: FSMContext):
    parsed = _parse_date(message.text)
    if parsed is None:
        await message.answer("Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ:")
        return

    repo: Repo = message.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(message.from_user.id)
    existing = await repo.get_diary_entry(user["id"], parsed)

    await state.update_data(selected_date=str(parsed), user_id=user["id"])

    if existing is None:
        # Нет записи — запускаем чекин
        await state.update_data(diary_data={})
        await _start_checkin(message, state, question_index=1)
    else:
        # Запись есть — предлагаем действия
        data = existing["data"] if isinstance(existing["data"], dict) else json.loads(existing["data"])
        await state.update_data(diary_data=data)
        await state.set_state(Diary.waiting_existing_action)
        await message.answer(
            f"📝 Запись за {parsed.strftime('%d.%m.%Y')} уже существует.\n"
            "Что вы хотите сделать?",
            reply_markup=existing_entry_kb(),
        )


async def _start_checkin(message_or_callback: Message | CallbackQuery, state: FSMContext, question_index: int = 1):
    """Начинает или продолжает процесс 5 вопросов."""
    q_name, q_text, _ = QUESTIONS[question_index - 1]
    await state.update_data(current_q=question_index)
    await state.set_state(Diary.waiting_score)

    text = f"Вопрос {question_index} из 5 — {q_name}\n{q_text}\n\nОцените от 1 до 10:"
    kb = score_kb(prefix="diary_score")

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=kb)
    else:
        await message_or_callback.answer(text, reply_markup=kb)


@router.callback_query(Diary.waiting_score, F.data.startswith("diary_score:"))
async def diary_score_selected(callback: CallbackQuery, state: FSMContext):
    _, _, score_str = callback.data.split(":")
    score = int(score_str)
    data = await _ensure_state_data(state)
    current_q = data.get("current_q", 1)

    await state.update_data(temp_score=score)
    await state.set_state(Diary.waiting_comment)

    # Подвопрос зависит от категории
    _, _, sub_question = QUESTIONS[current_q - 1]
    await callback.message.answer(
        f"Вы поставили {score}. {sub_question}"
    )
    await callback.answer()


@router.message(Diary.waiting_comment)
async def diary_comment_received(message: Message, state: FSMContext):
    data = await _ensure_state_data(state)
    current_q: int = data.get("current_q", 1)
    score: int = data.get("temp_score", 5)
    comment: str = message.text.strip()

    diary_data: dict = data.get("diary_data", {})
    diary_data[f"q{current_q}"] = {"score": score, "comment": comment}
    await state.update_data(diary_data=diary_data)

    if current_q < 5:
        # Переход к следующему вопросу
        await _start_checkin(message, state, question_index=current_q + 1)
    else:
        # Все вопросы отвечены — вычисляем Readiness Score
        readiness = _calc_readiness_score(diary_data)
        emoji = _readiness_emoji(readiness)

        selected_date_str: str = data.get("selected_date", str(date.today()))
        parsed_date = _parse_date(selected_date_str)
        user_id: int = data.get("user_id")
        repo: Repo = message.bot.get("repo")  # type: ignore

        existing = await repo.get_diary_entry(user_id, parsed_date)  # type: ignore
        if existing:
            await repo.update_diary_entry(user_id, parsed_date, diary_data, readiness)  # type: ignore
        else:
            await repo.create_diary_entry(user_id, parsed_date, diary_data, readiness)  # type: ignore

        # Определяем тренд по последним записям
        recent = await repo.get_recent_diary(user_id, days=7)
        # Преобразуем записи для функции тренда
        recent_for_trend = []
        for r in recent:
            d = r["data"] if isinstance(r["data"], dict) else json.loads(r["data"])
            recent_for_trend.append({
                "data": d,
                "readiness_score": float(r["readiness_score"]) if r["readiness_score"] else None,
            })
        trend = _detect_trend(recent_for_trend)

        await state.clear()

        # Формируем сводку
        q_names = [QUESTIONS[i][0] for i in range(5)]
        summary_lines = []
        for i, name in enumerate(q_names, 1):
            q = diary_data.get(f"q{i}", {})
            summary_lines.append(f"  {name}: {q.get('score', '—')} — {q.get('comment', '')}")

        await message.answer(
            f"✅ Запись дня сохранена!\n\n"
            f"{emoji} Readiness Score: {readiness}/10\n"
            f"Тренд: {trend}\n\n"
            f"📊 Сводка за день:\n" +
            "\n".join(summary_lines),
            reply_markup=main_menu_kb(),
        )


# ── Действия с существующей записью ────────────────────────

@router.callback_query(Diary.waiting_existing_action, F.data == "diary:rewrite")
async def diary_rewrite(callback: CallbackQuery, state: FSMContext):
    """Перезаписать: очистить JSON и запустить 5 вопросов заново."""
    await state.update_data(diary_data={})
    await _start_checkin(callback, state, question_index=1)
    await callback.answer("Перезапись начата")


@router.callback_query(Diary.waiting_existing_action, F.data == "diary:delete")
async def diary_delete_ask(callback: CallbackQuery, state: FSMContext):
    """Удаление записи — запрос подтверждения."""
    await state.set_state(Diary.waiting_delete_confirm)
    await callback.message.answer(
        "⚠️ Вы уверены, что хотите удалить запись за этот день?",
        reply_markup=confirm_kb(prefix="diary_del"),
    )
    await callback.answer()


@router.callback_query(Diary.waiting_delete_confirm, F.data.startswith("diary_del:"))
async def diary_delete_confirm(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    if action == "yes":
        data = await _ensure_state_data(state)
        parsed_date = _parse_date(data.get("selected_date", ""))
        user_id: int = data.get("user_id")
        repo: Repo = callback.bot.get("repo")  # type: ignore
        await repo.delete_diary_entry(user_id, parsed_date)  # type: ignore
        await state.clear()
        await callback.message.answer("🗑 Запись удалена.", reply_markup=main_menu_kb())
    else:
        await state.clear()
        await callback.message.answer("Отмена. Вы вернулись в главное меню.", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(Diary.waiting_existing_action, F.data == "diary:edit")
async def diary_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Меню изменения: клавиатура 1-5 / О-О..."""
    data = await _ensure_state_data(state)
    diary_data: dict = data.get("diary_data", {})
    await state.set_state(Diary.waiting_edit_question)
    await callback.message.answer(
        "Выберите вопрос для изменения оценки или комментария:",
        reply_markup=edit_questions_kb(diary_data, prefix="editq"),
    )
    await callback.answer()


@router.callback_query(Diary.waiting_edit_question, F.data.startswith("editq:"))
async def diary_edit_question(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action_type = parts[1]  # "score" или "comment"
    q_num = int(parts[2])   # 1-5

    if action_type == "done":
        # Сохраняем, пересчитываем Readiness и выходим
        data = await _ensure_state_data(state)
        diary_data: dict = data.get("diary_data", {})
        parsed_date = _parse_date(data.get("selected_date", ""))
        user_id: int = data.get("user_id")
        readiness = _calc_readiness_score(diary_data)
        repo: Repo = callback.bot.get("repo")  # type: ignore
        await repo.update_diary_entry(user_id, parsed_date, diary_data, readiness)  # type: ignore
        await state.clear()
        emoji = _readiness_emoji(readiness)
        await callback.message.answer(
            f"✅ Изменения сохранены! {emoji} Readiness: {readiness}/10",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    await state.update_data(edit_q_num=q_num, edit_action=action_type)

    data = await _ensure_state_data(state)
    diary_data = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_info = diary_data.get(q_key, {})
    q_name = QUESTIONS[q_num - 1][0]

    if action_type == "score":
        await state.set_state(Diary.waiting_edit_score)
        old_score = q_info.get("score", "—")
        await callback.message.answer(
            f"{q_name}: текущая оценка = {old_score}\nВыберите новую оценку:",
            reply_markup=score_kb(prefix="edit_score"),
        )
    elif action_type == "comment":
        await state.set_state(Diary.waiting_edit_comment)
        old_comment = q_info.get("comment", "—")
        await callback.message.answer(
            f"{q_name}: текущий комментарий = «{old_comment}»\n"
            "Введите новый комментарий:"
        )
    await callback.answer()


@router.callback_query(Diary.waiting_edit_score, F.data.startswith("edit_score:"))
async def diary_edit_score_save(callback: CallbackQuery, state: FSMContext):
    _, _, score_str = callback.data.split(":")
    new_score = int(score_str)
    data = await _ensure_state_data(state)
    q_num: int = data.get("edit_q_num", 1)
    diary_data: dict = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_name = QUESTIONS[q_num - 1][0]

    if q_key not in diary_data:
        diary_data[q_key] = {}
    diary_data[q_key]["score"] = new_score
    await state.update_data(diary_data=diary_data)

    await callback.message.answer(f"{q_name}: оценка обновлена на {new_score}.")
    # Возврат в меню редактирования
    await state.set_state(Diary.waiting_edit_question)
    await callback.message.answer(
        "Продолжите редактирование или нажмите «Готово»:",
        reply_markup=edit_questions_kb(diary_data, prefix="editq"),
    )
    await callback.answer()


@router.message(Diary.waiting_edit_comment)
async def diary_edit_comment_save(message: Message, state: FSMContext):
    data = await _ensure_state_data(state)
    q_num: int = data.get("edit_q_num", 1)
    diary_data: dict = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_name = QUESTIONS[q_num - 1][0]

    if q_key not in diary_data:
        diary_data[q_key] = {}
    diary_data[q_key]["comment"] = message.text.strip()
    await state.update_data(diary_data=diary_data)

    await message.answer(f"{q_name}: комментарий обновлён.")
    # Возврат в меню редактирования
    await state.set_state(Diary.waiting_edit_question)
    await message.answer(
        "Продолжите редактирование или нажмите «Готово»:",
        reply_markup=edit_questions_kb(diary_data, prefix="editq"),
    )


@router.callback_query(Diary.waiting_existing_action, F.data == "diary:add")
async def diary_add_menu(callback: CallbackQuery, state: FSMContext):
    """Меню добавления: клавиатура 1-5 / О-О..."""
    data = await _ensure_state_data(state)
    diary_data: dict = data.get("diary_data", {})
    await state.set_state(Diary.waiting_add_question)
    await callback.message.answer(
        "Выберите вопрос для добавления/изменения оценки или комментария:",
        reply_markup=add_questions_kb(diary_data, prefix="addq"),
    )
    await callback.answer()


@router.callback_query(Diary.waiting_add_question, F.data.startswith("addq:"))
async def diary_add_question(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action_type = parts[1]  # "score" или "comment"
    q_num = int(parts[2])

    if action_type == "done":
        data = await _ensure_state_data(state)
        diary_data: dict = data.get("diary_data", {})
        parsed_date = _parse_date(data.get("selected_date", ""))
        user_id: int = data.get("user_id")
        readiness = _calc_readiness_score(diary_data)
        repo: Repo = callback.bot.get("repo")  # type: ignore
        await repo.update_diary_entry(user_id, parsed_date, diary_data, readiness)  # type: ignore
        await state.clear()
        emoji = _readiness_emoji(readiness)
        await callback.message.answer(
            f"✅ Добавления сохранены! {emoji} Readiness: {readiness}/10",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    await state.update_data(add_q_num=q_num, add_action=action_type)

    data = await _ensure_state_data(state)
    diary_data = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_info = diary_data.get(q_key, {})
    q_name = QUESTIONS[q_num - 1][0]

    if action_type == "score":
        await state.set_state(Diary.waiting_add_score)
        old_score = q_info.get("score", "—")
        await callback.message.answer(
            f"{q_name}: текущая оценка = {old_score}\nВыберите новую оценку:",
            reply_markup=score_kb(prefix="add_score"),
        )
    elif action_type == "comment":
        await state.set_state(Diary.waiting_add_comment)
        old_comment = q_info.get("comment", "—")
        await callback.message.answer(
            f"{q_name}: текущий комментарий = «{old_comment}»\n"
            "Введите новый комментарий (перезапишет существующий):"
        )
    await callback.answer()


@router.callback_query(Diary.waiting_add_score, F.data.startswith("add_score:"))
async def diary_add_score_save(callback: CallbackQuery, state: FSMContext):
    _, _, score_str = callback.data.split(":")
    new_score = int(score_str)
    data = await _ensure_state_data(state)
    q_num: int = data.get("add_q_num", 1)
    diary_data: dict = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_name = QUESTIONS[q_num - 1][0]

    if q_key not in diary_data:
        diary_data[q_key] = {}
    diary_data[q_key]["score"] = new_score
    await state.update_data(diary_data=diary_data)

    await callback.message.answer(f"{q_name}: оценка обновлена на {new_score}.")
    await state.set_state(Diary.waiting_add_question)
    await callback.message.answer(
        "Продолжите добавление или нажмите «Готово»:",
        reply_markup=add_questions_kb(diary_data, prefix="addq"),
    )
    await callback.answer()


@router.message(Diary.waiting_add_comment)
async def diary_add_comment_save(message: Message, state: FSMContext):
    data = await _ensure_state_data(state)
    q_num: int = data.get("add_q_num", 1)
    diary_data: dict = data.get("diary_data", {})
    q_key = f"q{q_num}"
    q_name = QUESTIONS[q_num - 1][0]

    if q_key not in diary_data:
        diary_data[q_key] = {}
    diary_data[q_key]["comment"] = message.text.strip()
    await state.update_data(diary_data=diary_data)

    await message.answer(f"{q_name}: комментарий обновлён.")
    await state.set_state(Diary.waiting_add_question)
    await message.answer(
        "Продолжите добавление или нажмите «Готово»:",
        reply_markup=add_questions_kb(diary_data, prefix="addq"),
    )


# ════════════════════════════════════════════════════════════
#  В. Запланировать (Календарь)
# ════════════════════════════════════════════════════════════

@router.message(F.text == "Запланировать")
async def planner_menu(message: Message, state: FSMContext):
    await state.set_state(Planner.waiting_action)
    await message.answer("📅 Управление событиями:", reply_markup=planner_action_kb())


# ── Добавить событие ────────────────────────────────────────

@router.callback_query(Planner.waiting_action, F.data == "plan:add")
async def planner_add_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Planner.waiting_date)
    await state.update_data(plan_action="add")
    await callback.message.answer("Введите дату события (ДД.ММ.ГГГГ):")
    await callback.answer()


@router.message(Planner.waiting_date)
async def planner_process_date(message: Message, state: FSMContext):
    parsed = _parse_date(message.text)
    if parsed is None:
        await message.answer("Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ:")
        return

    data = await _ensure_state_data(state)
    action: str = data.get("plan_action", "add")
    await state.update_data(selected_date=str(parsed))

    if action == "add":
        await state.set_state(Planner.waiting_time)
        await message.answer("⏰ Введите время (ЧЧ:ММ):")
    elif action in ("edit", "delete"):
        # Показываем список событий на дату
        repo: Repo = message.bot.get("repo")  # type: ignore
        user = await repo.get_user_by_tg(message.from_user.id)
        events = await repo.get_events_by_date(user["id"], parsed)
        if not events:
            await message.answer("На эту дату нет событий.")
            await state.clear()
            await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_kb())
            return

        events_list = [
            {
                "id": e["id"],
                "time": str(e["time"]),
                "name": e["name"],
                "event_type": e.get("event_type", "routine"),
            }
            for e in events
        ]
        await state.update_data(events_list=events_list, events_page=0)
        await state.set_state(Planner.waiting_event_choice)
        await message.answer(
            "Выберите событие:",
            reply_markup=events_list_kb(events_list, page=0, prefix="pevt"),
        )


@router.message(Planner.waiting_time)
async def planner_add_time(message: Message, state: FSMContext):
    parsed = _parse_time(message.text)
    if parsed is None:
        await message.answer("Не удалось распознать время. Используйте формат ЧЧ:ММ:")
        return
    await state.update_data(event_time=str(parsed))
    await state.set_state(Planner.waiting_name)
    await message.answer("📝 Введите название события:")


@router.message(Planner.waiting_name)
async def planner_add_name(message: Message, state: FSMContext):
    await state.update_data(event_name=message.text.strip())
    await state.set_state(Planner.waiting_description)
    await message.answer("📄 Введите описание события:")


@router.message(Planner.waiting_description)
async def planner_add_description(message: Message, state: FSMContext):
    await state.update_data(event_description=message.text.strip())
    await state.set_state(Planner.waiting_event_type)
    await message.answer(
        "🏷 Выберите тип события:",
        reply_markup=event_type_kb(),
    )


@router.callback_query(Planner.waiting_event_type, F.data.startswith("etype:"))
async def planner_add_event_type(callback: CallbackQuery, state: FSMContext):
    event_type = callback.data.split(":")[1]
    await state.update_data(event_type_val=event_type)
    await state.set_state(Planner.waiting_priority)
    await callback.message.answer(
        "⚡ Выберите приоритет (1-10):",
        reply_markup=score_kb(prefix="plan_pri"),
    )
    await callback.answer()


@router.callback_query(Planner.waiting_priority, F.data.startswith("plan_pri:"))
async def planner_add_priority(callback: CallbackQuery, state: FSMContext):
    _, _, pri_str = callback.data.split(":")
    priority = int(pri_str)
    data = await _ensure_state_data(state)

    repo: Repo = callback.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(callback.from_user.id)
    parsed_date = _parse_date(data.get("selected_date", ""))
    parsed_time = _parse_time(data.get("event_time", "12:00"))
    event_type = data.get("event_type_val", "routine")

    await repo.create_event(
        user_id=user["id"],
        event_date=parsed_date,  # type: ignore
        event_time=parsed_time,  # type: ignore
        name=data.get("event_name", ""),
        description=data.get("event_description", ""),
        priority=priority,
        event_type=event_type,
    )

    type_label = EVENT_TYPES.get(event_type, event_type)
    await state.clear()
    await callback.message.answer(
        f"✅ Событие создано!\nТип: {type_label}",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# ── Выбор события (изменить / удалить) ─────────────────────

@router.callback_query(Planner.waiting_event_choice, F.data.startswith("pevt:"))
async def planner_event_choice(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")

    # Пагинация
    if parts[1] == "page":
        page = int(parts[2])
        data = await _ensure_state_data(state)
        events_list: list = data.get("events_list", [])
        await callback.message.edit_reply_markup(
            reply_markup=events_list_kb(events_list, page=page, prefix="pevt")
        )
        await callback.answer()
        return

    # Выбор конкретного события
    event_id = int(parts[2])
    data = await _ensure_state_data(state)
    action: str = data.get("plan_action", "edit")

    if action == "delete":
        await state.update_data(delete_event_id=event_id)
        await state.set_state(Planner.waiting_delete_confirm)
        await callback.message.answer(
            "⚠️ Удалить это событие?",
            reply_markup=confirm_kb(prefix="plan_del"),
        )
    elif action == "edit":
        await state.update_data(edit_event_id=event_id)
        await state.set_state(Planner.waiting_edit_field)
        await callback.message.answer(
            "Выберите поле для изменения:",
            reply_markup=event_edit_field_kb(),
        )
    await callback.answer()


@router.callback_query(Planner.waiting_delete_confirm, F.data.startswith("plan_del:"))
async def planner_delete_confirm(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    if action == "yes":
        data = await _ensure_state_data(state)
        event_id: int = data.get("delete_event_id", 0)
        repo: Repo = callback.bot.get("repo")  # type: ignore
        await repo.delete_event(event_id)
        await state.clear()
        await callback.message.answer("🗑 Событие удалено.", reply_markup=main_menu_kb())
    else:
        await state.clear()
        await callback.message.answer("Отмена. Вы вернулись в главное меню.", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(Planner.waiting_edit_field, F.data.startswith("efield:"))
async def planner_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)

    if field == "priority":
        await state.set_state(Planner.waiting_edit_value)
        await callback.message.answer(
            "Выберите новый приоритет (1-10):",
            reply_markup=score_kb(prefix="edit_pri"),
        )
    elif field == "event_type":
        await state.set_state(Planner.waiting_edit_value)
        await callback.message.answer(
            "Выберите новый тип события:",
            reply_markup=event_type_kb(),
        )
    else:
        hints = {
            "event_date": "Введите новую дату (ДД.ММ.ГГГГ):",
            "time": "Введите новое время (ЧЧ:ММ):",
            "name": "Введите новое название:",
            "description": "Введите новое описание:",
        }
        await state.set_state(Planner.waiting_edit_value)
        await callback.message.answer(hints.get(field, "Введите новое значение:"))
    await callback.answer()


@router.callback_query(Planner.waiting_edit_value, F.data.startswith("edit_pri:"))
async def planner_edit_priority_save(callback: CallbackQuery, state: FSMContext):
    _, _, pri_str = callback.data.split(":")
    priority = int(pri_str)
    data = await _ensure_state_data(state)
    event_id: int = data.get("edit_event_id", 0)
    repo: Repo = callback.bot.get("repo")  # type: ignore
    await repo.update_event_field(event_id, "priority", priority)
    await state.clear()
    await callback.message.answer("✅ Приоритет обновлён!", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(Planner.waiting_edit_value, F.data.startswith("etype:"))
async def planner_edit_event_type_save(callback: CallbackQuery, state: FSMContext):
    event_type = callback.data.split(":")[1]
    data = await _ensure_state_data(state)
    event_id: int = data.get("edit_event_id", 0)
    repo: Repo = callback.bot.get("repo")  # type: ignore
    await repo.update_event_field(event_id, "event_type", event_type)
    type_label = EVENT_TYPES.get(event_type, event_type)
    await state.clear()
    await callback.message.answer(
        f"✅ Тип события обновлён на: {type_label}",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.message(Planner.waiting_edit_value)
async def planner_edit_value_save(message: Message, state: FSMContext):
    data = await _ensure_state_data(state)
    field: str = data.get("edit_field", "")
    event_id: int = data.get("edit_event_id", 0)

    value = message.text.strip()

    # Парсинг в зависимости от типа поля
    if field == "event_date":
        parsed = _parse_date(value)
        if parsed is None:
            await message.answer("Не удалось распознать дату. Используйте ДД.ММ.ГГГГ:")
            return
        value = parsed
    elif field == "time":
        parsed = _parse_time(value)
        if parsed is None:
            await message.answer("Не удалось распознать время. Используйте ЧЧ:ММ:")
            return
        value = parsed
    elif field == "priority":
        try:
            value = int(value)
        except ValueError:
            await message.answer("Введите число от 1 до 10:")
            return

    repo: Repo = message.bot.get("repo")  # type: ignore
    await repo.update_event_field(event_id, field, value)

    await state.clear()
    await message.answer("✅ Событие обновлено!", reply_markup=main_menu_kb())


# ════════════════════════════════════════════════════════════
#  Г. Циклы (DeepSeek)
# ════════════════════════════════════════════════════════════

@router.message(F.text == "Циклы")
async def cycles_menu(message: Message, state: FSMContext):
    await state.set_state(Cycles.waiting_action)
    await message.answer("🔮 Анализ циклов продуктивности:", reply_markup=cycles_menu_kb())


@router.callback_query(Cycles.waiting_action, F.data == "cycle:calc")
async def cycles_calculate(callback: CallbackQuery, state: FSMContext):
    """Рассчитать прогноз на 10 дней через DeepSeek."""
    repo: Repo = callback.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(callback.from_user.id)

    await callback.message.answer("⏳ Формирую прогноз, это может занять несколько секунд...")

    history = await repo.get_all_history_and_events(user["id"])

    if not history["diary"] and not history["events"]:
        await callback.message.answer(
            "У вас пока нет данных для анализа. Заполните дневник или добавьте события."
        )
        await callback.answer()
        return

    # Добавляем тренд в промпт
    recent = await repo.get_recent_diary(user["id"], days=7)
    recent_for_trend = []
    for r in recent:
        d = r["data"] if isinstance(r["data"], dict) else json.loads(r["data"])
        recent_for_trend.append({
            "data": d,
            "readiness_score": float(r["readiness_score"]) if r["readiness_score"] else None,
        })
    trend = _detect_trend(recent_for_trend)

    prompt = _build_diary_prompt(history, history)
    prompt += f"\n\nТекущий тренд Readiness: {trend}"

    try:
        report = await deepseek_service.predict(prompt)
    except Exception as e:
        logger.error("DeepSeek error: %s", e)
        await callback.message.answer(
            "❌ Ошибка при обращении к AI. Попробуйте позже."
        )
        await callback.answer()
        return

    # Сохраняем прогноз
    await repo.create_prediction(user["id"], report)

    # Отправляем пользователю (с разбивкой на части, если длинный)
    for part in _split_long_message(report):
        await callback.message.answer(part)

    await state.clear()
    await callback.message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(Cycles.waiting_action, F.data == "cycle:last")
async def cycles_show_last(callback: CallbackQuery, state: FSMContext):
    """Показать последний расчёт."""
    repo: Repo = callback.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(callback.from_user.id)

    prediction = await repo.get_last_prediction(user["id"])
    if prediction is None:
        await callback.message.answer("У вас пока нет расчётов.")
    else:
        for part in _split_long_message(prediction["report"]):
            await callback.message.answer(part)

    await callback.answer()


@router.callback_query(Cycles.waiting_action, F.data == "cycle:feedback")
async def cycles_feedback_start(callback: CallbackQuery, state: FSMContext):
    """Оценить расчёт — шаг 1: ввод даты."""
    await state.set_state(Cycles.waiting_feedback_date)
    await callback.message.answer(
        "📋 Скопируйте текст рекомендации из чата и вставьте его сюда,\n"
        "затем напишите дату прогноза (ДД.ММ.ГГГГ):"
    )
    await callback.answer()


@router.message(Cycles.waiting_feedback_date)
async def cycles_feedback_date(message: Message, state: FSMContext):
    # Сохраняем текст (в прототипе используем его как контекст)
    await state.update_data(feedback_text=message.text.strip())

    repo: Repo = message.bot.get("repo")  # type: ignore
    user = await repo.get_user_by_tg(message.from_user.id)
    prediction = await repo.get_last_prediction(user["id"])

    if prediction is None:
        await state.clear()
        await message.answer("У вас нет прогнозов для оценки.", reply_markup=main_menu_kb())
        return

    await state.update_data(prediction_id=prediction["id"])
    await state.set_state(Cycles.waiting_feedback_applied)
    await message.answer("Вы применили рекомендацию?", reply_markup=feedback_applied_kb())


@router.callback_query(Cycles.waiting_feedback_applied, F.data.startswith("fb:applied:"))
async def cycles_feedback_applied(callback: CallbackQuery, state: FSMContext):
    applied = callback.data.split(":")[2] == "yes"
    await state.update_data(feedback_applied=applied)
    await state.set_state(Cycles.waiting_feedback_result)
    await callback.message.answer("Опишите результат кратко:")
    await callback.answer()


@router.message(Cycles.waiting_feedback_result)
async def cycles_feedback_result(message: Message, state: FSMContext):
    data = await _ensure_state_data(state)
    prediction_id: int = data.get("prediction_id", 0)
    applied: bool = data.get("feedback_applied", False)

    feedback = {
        "applied": applied,
        "result": message.text.strip(),
        "text": data.get("feedback_text", ""),
    }

    repo: Repo = message.bot.get("repo")  # type: ignore
    await repo.update_prediction_feedback(prediction_id, feedback)

    await state.clear()
    await message.answer("✅ Спасибо за обратную связь!", reply_markup=main_menu_kb())


# ════════════════════════════════════════════════════════════
#  Игнорирование текста, не совпадающего с кнопками меню
# ════════════════════════════════════════════════════════════

MAIN_MENU_BUTTONS = {"Настройки", "Записать день", "Запланировать", "Циклы", "🔙 Назад"}

SETTINGS_BUTTONS = {"Изменить Имя", "🔙 Назад"}


@router.message(F.text)
async def ignore_unmatched_text(message: Message, state: FSMContext):
    """
    Если пользователь ввёл текст, который не совпадает с кнопками меню
    и при этом активна клавиатура — игнорируем.
    Данный хэндлер должен быть последним в роутере.
    """
    current_state = await state.get_state()
    # Если пользователь не в FSM-сценарии — просто игнорируем
    if current_state is None:
        if message.text not in MAIN_MENU_BUTTONS:
            return
    # Если внутри FSM — не перехватываем (обработают специализированные хэндлеры)
