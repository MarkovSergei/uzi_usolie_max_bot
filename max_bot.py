import asyncio
import requests
import urllib3
from datetime import datetime, timedelta

import config
import database

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://platform-api2.max.ru"
HEADERS = {"Authorization": config.MAX_BOT_TOKEN}

# ------------------------- ОТПРАВКА -------------------------

def send_message(chat_id, text, buttons=None):
    """Отправка сообщения в MAX."""
    url = f"{API_URL}/messages"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if buttons:
        payload["attachments"] = [{
            "type": "inline_keyboard",
            "payload": {"buttons": buttons}
        }]

    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10, verify=False)
        return response.json()
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return None

def make_button(text, callback_data=None, url=None, link=False):
    """Создание кнопки."""
    if link:
        return {"type": "link", "text": text, "url": url}
    return {"type": "callback", "text": text, "payload": callback_data}

# ------------------------- КЛАВИАТУРЫ -------------------------

def main_keyboard():
    return [
        [make_button("🩺 Виды УЗИ и цены", "menu_services")],
        [make_button("❓ Вопросы и ответы", "menu_faq")],
        [make_button("📅 Запланировать визит", "menu_plan")],
        [make_button("🔔 Мои напоминания", "menu_reminders")],
        [make_button("📍 Контакты и график", "menu_contacts")],
    ]

def back_keyboard(callback_data="menu_main"):
    return [[make_button("← Назад", callback_data)]]

# ------------------------- ОБРАБОТКА -------------------------

def process_update(update):
    update_type = update.get("update_type")
    chat_id = update.get("chat_id")

    if update_type == "bot_started":
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (str(chat_id),))
        conn.commit()
        conn.close()

        text = (
            "Здравствуйте!\n\n"
            "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
            "Помогу узнать цены, подготовку к исследованиям и напомню о плановом визите.\n\n"
            "Выберите действие в меню:"
        )
        send_message(chat_id, text, main_keyboard())

    elif update_type == "message_created":
        text = update.get("body", {}).get("text", "")
        if text == "/start":
            conn = database.get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (str(chat_id),))
            conn.commit()
            conn.close()

            welcome = (
                "Здравствуйте!\n\n"
                "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
                "Помогу узнать цены, подготовку к исследованиям и напомню о плановом визите.\n\n"
                "Выберите действие в меню:"
            )
            send_message(chat_id, welcome, main_keyboard())

    elif update_type == "message_callback":
        payload = update.get("payload", "")
        process_callback(chat_id, payload)

def process_callback(chat_id, payload):
    if payload == "menu_services":
        show_services(chat_id)
    elif payload.startswith("service_"):
        show_service_detail(chat_id, int(payload.split("_")[1]))
    elif payload == "menu_faq":
        show_faq(chat_id)
    elif payload.startswith("faq_"):
        show_faq_answer(chat_id, int(payload.split("_")[1]))
    elif payload == "menu_plan":
        show_plan_services(chat_id)
    elif payload.startswith("plan_service_"):
        show_plan_periods(chat_id, int(payload.split("_")[2]))
    elif payload.startswith("period_"):
        save_plan_reminder(chat_id, int(payload.split("_")[1]), payload.split("_")[2])
    elif payload.startswith("upd_"):
        update_reminder(chat_id, int(payload.split("_")[1]), payload.split("_")[2])
    elif payload == "menu_reminders":
        show_my_reminders(chat_id)
    elif payload == "menu_contacts":
        show_contacts(chat_id)
    elif payload == "menu_main":
        send_message(chat_id, "Главное меню:", main_keyboard())

# ------------------------- РАЗДЕЛЫ -------------------------

def show_services(chat_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services WHERE is_active = 1 ORDER BY name")
    services = cursor.fetchall()
    conn.close()

    if not services:
        send_message(chat_id, "Список пока пуст.")
        return

    buttons = []
    for s in services:
        buttons.append([make_button(s["name"], f"service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])

    send_message(chat_id, "Выберите исследование:", buttons)

def show_service_detail(chat_id, service_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, price, preparation FROM services WHERE id = ?", (service_id,))
    service = cursor.fetchone()
    conn.close()

    if not service:
        send_message(chat_id, "Исследование не найдено.")
        return

    text = f"🩺 {service['name']}\n\n"
    if service["description"]:
        text += f"ℹ️ {service['description']}\n\n"
    text += f"💰 Цена: {service['price']}\n\n"
    if service["preparation"]:
        text += f"📋 Подготовка:\n{service['preparation']}"

    send_message(chat_id, text, back_keyboard("menu_services"))

def show_faq(chat_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question FROM faq ORDER BY sort_order")
    faqs = cursor.fetchall()
    conn.close()

    if not faqs:
        send_message(chat_id, "Вопросы пока не добавлены.")
        return

    buttons = []
    for f in faqs:
        buttons.append([make_button(f["question"], f"faq_{f['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])

    send_message(chat_id, "Частые вопросы:", buttons)

def show_faq_answer(chat_id, faq_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer FROM faq WHERE id = ?", (faq_id,))
    faq = cursor.fetchone()
    conn.close()

    if not faq:
        send_message(chat_id, "Вопрос не найден.")
        return

    text = f"❓ {faq['question']}\n\n{faq['answer']}"
    send_message(chat_id, text, back_keyboard("menu_faq"))

def show_plan_services(chat_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services WHERE is_active = 1 ORDER BY name")
    services = cursor.fetchall()
    conn.close()

    if not services:
        send_message(chat_id, "Список пока пуст.")
        return

    buttons = []
    for s in services:
        buttons.append([make_button(s["name"], f"plan_service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])

    send_message(chat_id, "Выберите исследование:", buttons)

def show_plan_periods(chat_id, service_id):
    buttons = [
        [make_button("1 месяц", f"period_{service_id}_1")],
        [make_button("3 месяца", f"period_{service_id}_3")],
        [make_button("6 месяцев", f"period_{service_id}_6")],
        [make_button("12 месяцев", f"period_{service_id}_12")],
        [make_button("← Назад", "menu_plan")],
    ]
    send_message(chat_id, "Через сколько напомнить?", buttons)

def save_plan_reminder(chat_id, service_id, period):
    months = int(period)
    remind_date = (datetime.now() + timedelta(days=months * 30)).strftime("%d.%m.%Y")

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT remind_date FROM reminders WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
        (str(chat_id), service_id)
    )
    existing = cursor.fetchone()

    if existing:
        buttons = [
            [make_button("Да, обновить", f"upd_{service_id}_{remind_date}")],
            [make_button("Отмена", "menu_main")],
        ]
        send_message(chat_id, f"Уже запланировано на {existing['remind_date']}. Обновить?", buttons)
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
    send_message(chat_id, text, main_keyboard())

def update_reminder(chat_id, service_id, remind_date):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE reminders SET remind_date = ? WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
        (remind_date, str(chat_id), service_id)
    )
    conn.commit()
    conn.close()

    send_message(chat_id, f"✅ Дата обновлена!\n\nНапомню: {remind_date}", main_keyboard())

def show_my_reminders(chat_id):
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
        send_message(chat_id, "У вас нет активных напоминаний.")
        return

    text = "Ваши напоминания:\n\n"
    for r in reminders:
        text += f"• {r['name']} — {r['remind_date']}\n"

    send_message(chat_id, text, main_keyboard())

def show_contacts(chat_id):
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

    buttons = [
        [make_button("🗺 Открыть на карте", url=settings.get("map_link", ""), link=True)],
        [make_button("📲 Задать вопрос врачу", url="https://t.me/MarkovSerge", link=True)],
    ]

    send_message(chat_id, text, buttons)

# ------------------------- ЗАПУСК -------------------------

async def run_max_bot():
    print("MAX BOT STARTED")

    # Проверка токена
    try:
        response = requests.get(f"{API_URL}/me", headers=HEADERS, timeout=10, verify=False)
        print(f"MAX /me status: {response.status_code}")
        print(f"MAX /me response: {response.text}")
    except Exception as e:
        print(f"MAX /me error: {e}")

    # Long Polling
    offset = 0
    while True:
        try:
            url = f"{API_URL}/updates"
            params = {"offset": offset}
            response = requests.get(url, headers=HEADERS, params=params, timeout=60, verify=False)
            data = response.json()
            print(f"MAX updates: {data}")

            updates = data.get("updates", [])
            for update in updates:
                process_update(update)
                offset = max(offset, update.get("update_id", 0) + 1)

        except Exception as e:
            print(f"Ошибка polling MAX: {e}")

        await asyncio.sleep(2)
