import asyncio
from datetime import datetime, timedelta
from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart

import config
import database

bot = Bot(token=config.MAX_BOT_TOKEN)
dp = Dispatcher()

# ------------------------- КЛАВИАТУРЫ -------------------------

def get_main_keyboard():
    """Главное меню для Макс."""
    return {
        "inline_keyboard": [
            [{"text": "🩺 Виды УЗИ и цены", "callback_data": "menu_services"}],
            [{"text": "❓ Вопросы и ответы", "callback_data": "menu_faq"}],
            [{"text": "📅 Запланировать визит", "callback_data": "menu_plan"}],
            [{"text": "🔔 Мои напоминания", "callback_data": "menu_reminders"}],
            [{"text": "📍 Контакты и график", "callback_data": "menu_contacts"}],
        ]
    }

def get_back_keyboard(callback_data="menu_main"):
    """Клавиатура с кнопкой Назад."""
    return {
        "inline_keyboard": [
            [{"text": "← Назад", "callback_data": callback_data}],
        ]
    }

# ------------------------- ОБРАБОТЧИКИ -------------------------

@dp.bot_started()
async def on_start(event):
    """Обработка старта."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (chat_id) VALUES (?)",
        (str(chat_id),)
    )
    conn.commit()
    conn.close()

    text = (
        "Здравствуйте!\n\n"
        "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
        "Помогу узнать цены, подготовку к исследованиям и напомню о плановом визите.\n\n"
        "Выберите действие в меню:"
    )
    await bot.send_message(chat_id=chat_id, text=text, attachments=[get_main_keyboard()])


@dp.message_created(CommandStart())
async def on_start_command(event):
    """Обработка /start."""
    await on_start(event)


@dp.callback_query(F.data == "menu_services")
async def services_list(event):
    """Список исследований."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services WHERE is_active = 1 ORDER BY name")
    services = cursor.fetchall()
    conn.close()

    if not services:
        await bot.send_message(chat_id=chat_id, text="Список пока пуст.")
        return

    keyboard = []
    for s in services:
        keyboard.append([{"text": s["name"], "callback_data": f"service_{s['id']}"}])
    keyboard.append([{"text": "← Назад", "callback_data": "menu_main"}])

    await bot.send_message(
        chat_id=chat_id,
        text="Выберите исследование:",
        attachments=[{"inline_keyboard": keyboard}]
    )


@dp.callback_query(F.data.startswith("service_"))
async def service_detail(event):
    """Детали исследования."""
    service_id = int(event.data.split("_")[1])
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, description, price, preparation FROM services WHERE id = ?",
        (service_id,)
    )
    service = cursor.fetchone()
    conn.close()

    if not service:
        await bot.send_message(chat_id=chat_id, text="Исследование не найдено.")
        return

    text = f"🩺 {service['name']}\n\n"

    if service["description"]:
        text += f"ℹ️ {service['description']}\n\n"

    text += f"💰 Цена: {service['price']}\n\n"

    if service["preparation"]:
        text += f"📋 Подготовка:\n{service['preparation']}"

    keyboard = {"inline_keyboard": [[{"text": "← Назад к списку", "callback_data": "menu_services"}]]}

    await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard])


@dp.callback_query(F.data == "menu_faq")
async def faq_list(event):
    """Список вопросов."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question FROM faq ORDER BY sort_order")
    faqs = cursor.fetchall()
    conn.close()

    if not faqs:
        await bot.send_message(chat_id=chat_id, text="Вопросы пока не добавлены.")
        return

    keyboard = []
    for f in faqs:
        keyboard.append([{"text": f["question"], "callback_data": f"faq_{f['id']}"}])
    keyboard.append([{"text": "← Назад", "callback_data": "menu_main"}])

    await bot.send_message(
        chat_id=chat_id,
        text="Частые вопросы:",
        attachments=[{"inline_keyboard": keyboard}]
    )


@dp.callback_query(F.data.startswith("faq_"))
async def faq_answer(event):
    """Ответ на вопрос."""
    faq_id = int(event.data.split("_")[1])
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer FROM faq WHERE id = ?", (faq_id,))
    faq = cursor.fetchone()
    conn.close()

    if not faq:
        await bot.send_message(chat_id=chat_id, text="Вопрос не найден.")
        return

    text = f"❓ {faq['question']}\n\n{faq['answer']}"

    keyboard = {"inline_keyboard": [[{"text": "← Назад к вопросам", "callback_data": "menu_faq"}]]}

    await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard])


@dp.callback_query(F.data == "menu_plan")
async def plan_start(event):
    """Начало планирования."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services WHERE is_active = 1 ORDER BY name")
    services = cursor.fetchall()
    conn.close()

    if not services:
        await bot.send_message(chat_id=chat_id, text="Список исследований пока пуст.")
        return

    keyboard = []
    for s in services:
        keyboard.append([{"text": s["name"], "callback_data": f"plan_service_{s['id']}"}])
    keyboard.append([{"text": "← Назад", "callback_data": "menu_main"}])

    await bot.send_message(
        chat_id=chat_id,
        text="Выберите исследование:",
        attachments=[{"inline_keyboard": keyboard}]
    )


@dp.callback_query(F.data.startswith("plan_service_"))
async def plan_service_chosen(event):
    """Исследование выбрано."""
    service_id = int(event.data.split("_")[2])
    chat_id = event.chat_id

    # Сохраняем во временное хранилище
    # Для простоты — передадим через callback_data
    keyboard = {
        "inline_keyboard": [
            [{"text": "1 месяц", "callback_data": f"period_{service_id}_1"}],
            [{"text": "3 месяца", "callback_data": f"period_{service_id}_3"}],
            [{"text": "6 месяцев", "callback_data": f"period_{service_id}_6"}],
            [{"text": "12 месяцев", "callback_data": f"period_{service_id}_12"}],
            [{"text": "← Назад", "callback_data": "menu_plan"}],
        ]
    }

    await bot.send_message(chat_id=chat_id, text="Через сколько напомнить?", attachments=[keyboard])


@dp.callback_query(F.data.startswith("period_"))
async def plan_period_chosen(event):
    """Период выбран."""
    parts = event.data.split("_")
    service_id = int(parts[1])
    period = parts[2]
    chat_id = event.chat_id

    months = int(period)
    remind_date = (datetime.now() + timedelta(days=months * 30)).strftime("%d.%m.%Y")

    # Сохраняем напоминание
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT remind_date FROM reminders WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
        (str(chat_id), service_id)
    )
    existing = cursor.fetchone()

    if existing:
        keyboard = {"inline_keyboard": [
            [{"text": "Да, обновить", "callback_data": f"upd_{service_id}_{remind_date}"}],
            [{"text": "Отмена", "callback_data": "menu_main"}],
        ]}
        await bot.send_message(
            chat_id=chat_id,
            text=f"Уже запланировано на {existing['remind_date']}. Обновить?",
            attachments=[keyboard]
        )
        conn.close()
        return

    cursor.execute(
        "INSERT INTO reminders (chat_id, service_id, remind_date) VALUES (?, ?, ?)",
        (str(chat_id), service_id, remind_date)
    )
    conn.commit()

    cursor.execute("SELECT name FROM services WHERE id = ?", (service_id,))
    service = cursor.fetchone()
    conn.close()

    text = (
        "✅ Запланировано!\n\n"
        f"Исследование: {service['name']}\n"
        f"Напомню: {remind_date}\n\n"
        "За день до визита пришлю напоминание."
    )

    await bot.send_message(chat_id=chat_id, text=text, attachments=[get_main_keyboard()])


@dp.callback_query(F.data.startswith("upd_"))
async def update_reminder(event):
    """Обновление напоминания."""
    parts = event.data.split("_")
    service_id = int(parts[1])
    remind_date = parts[2]
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE reminders SET remind_date = ? WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
        (remind_date, str(chat_id), service_id)
    )
    conn.commit()
    conn.close()

    await bot.send_message(
        chat_id=chat_id,
        text=f"✅ Дата обновлена!\n\nНапомню: {remind_date}",
        attachments=[get_main_keyboard()]
    )


@dp.callback_query(F.data == "menu_reminders")
async def my_reminders(event):
    """Список напоминаний."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.remind_date, s.name
        FROM reminders r
        JOIN services s ON r.service_id = s.id
        WHERE r.chat_id = ? AND r.is_sent = 0
        ORDER BY r.remind_date
        """,
        (str(chat_id),)
    )
    reminders = cursor.fetchall()
    conn.close()

    if not reminders:
        await bot.send_message(chat_id=chat_id, text="У вас нет активных напоминаний.")
        return

    text = "Ваши напоминания:\n\n"
    for r in reminders:
        text += f"• {r['name']} — {r['remind_date']}\n"

    await bot.send_message(chat_id=chat_id, text=text, attachments=[get_main_keyboard()])


@dp.callback_query(F.data == "menu_contacts")
async def contacts(event):
    """Контакты."""
    chat_id = event.chat_id

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('address', 'work_hours', 'phone', 'map_link')")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    text = (
        f"📍 Адрес: {settings.get('address', '')}\n\n"
        f"🕒 Часы работы: {settings.get('work_hours', '')}\n\n"
        f"📞 Телефон: {settings.get('phone', '')}"
    )

    keyboard = {"inline_keyboard": [
        [{"text": "🗺 Открыть на карте", "url": settings.get("map_link", "")}],
        [{"text": "📲 Задать вопрос врачу", "url": "https://t.me/MarkovSerge"}],
    ]}

    await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard])


@dp.callback_query(F.data == "menu_main")
async def menu_main(event):
    """Главное меню."""
    chat_id = event.chat_id
    await bot.send_message(chat_id=chat_id, text="Главное меню:", attachments=[get_main_keyboard()])


# ------------------------- ЗАПУСК -------------------------

async def run_max_bot():
    """Запуск polling для Макс."""
    await dp.start_polling(bot)
