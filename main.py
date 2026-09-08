"""
Полный бот для MAX с меню, услугами, FAQ и контактами.
С базой данных SQLite для хранения напоминаний.
"""
import subprocess
import sys
import os

def install(package):
    """Установка пакета через pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Ошибка установки {package}: {e}")

# Пытаемся импортировать Flask, если нет - устанавливаем
try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Flask не найден, устанавливаю...")
    install("flask")
    install("requests")
    from flask import Flask, request, jsonify

import json
import logging
import requests
import sqlite3
from datetime import datetime, timedelta
import threading
import time

# ==================== НАСТРОЙКА ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("max-bot")

app = Flask(__name__)

MAX_API = "https://platform-api.max.ru"
TOKEN = (os.environ.get("MAX_BOT_TOKEN") or "").strip()
USE_BEARER = os.environ.get("MAX_USE_BEARER", "").lower() in ("1", "true", "yes")

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.db")

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Создаем таблицу напоминаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            remind_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_sent INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

def save_reminder_to_db(user_id, service_name, remind_date):
    """Сохранить напоминание в базу данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reminders (user_id, service_name, remind_date, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, service_name, remind_date, datetime.now().strftime("%d.%m.%Y %H:%M")))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Напоминание сохранено в БД: {service_name} на {remind_date}")

def get_reminders_from_db(user_id):
    """Получить напоминания пользователя из БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, service_name, remind_date, created_at, is_sent
        FROM reminders
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    
    reminders = cursor.fetchall()
    conn.close()
    
    result = []
    for r in reminders:
        result.append({
            "id": r[0],
            "service_name": r[1],
            "remind_date": r[2],
            "created_at": r[3],
            "is_sent": r[4]
        })
    
    return result

def delete_all_reminders_from_db(user_id):
    """Удалить все напоминания пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM reminders WHERE user_id = ?', (user_id,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"🗑 Удалено {deleted} напоминаний для user_id={user_id}")
    return deleted

def get_unsent_reminders_for_tomorrow():
    """Получить неотправленные напоминания на завтра"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, user_id, service_name, remind_date
        FROM reminders
        WHERE remind_date = ? AND is_sent = 0
    ''', (tomorrow,))
    
    reminders = cursor.fetchall()
    conn.close()
    
    result = []
    for r in reminders:
        result.append({
            "id": r[0],
            "user_id": r[1],
            "service_name": r[2],
            "remind_date": r[3]
        })
    
    return result

def mark_reminder_as_sent(reminder_id):
    """Отметить напоминание как отправленное"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE reminders SET is_sent = 1 WHERE id = ?', (reminder_id,))
    
    conn.commit()
    conn.close()

# ==================== ДАННЫЕ ====================

SERVICES = [
    {
        "id": 1,
        "name": "УЗИ органов брюшной полости",
        "description": "Комплексное исследование органов брюшной полости и забрюшинного пространства.\nВходят: печень, желчный пузырь, поджелудочная железа, селезенка, почки, мочевой пузырь.\n\nПоказания: боли в животе, тяжесть после еды, тошнота, горечь во рту, подозрение на камни, контроль хронических заболеваний.",
        "price": "2000 руб.",
        "preparation": "За 2–3 дня: исключите продукты, вызывающие вздутие — свежий хлеб, бобовые, капусту, газированные напитки, сырые овощи и фрукты.\nПри склонности к метеоризму можно принимать эспумизан.\n\nВ день исследования: приходите натощак. Утром не есть и не пить."
    },
    {
        "id": 2,
        "name": "УЗИ почек и мочевого пузыря",
        "description": "Исследование почек и мочевого пузыря.\nПоказания: боли в пояснице, отёки, изменения в анализах мочи, подозрение на камни, кисты, новообразования.",
        "price": "1500 руб.",
        "preparation": "За 2–3 дня: исключите газообразующие продукты — бобовые, капусту, газировку, свежую выпечку.\n\nВ день исследования: натощак — не пить и не есть.\nЕсли нужно посмотреть мочевой пузырь: с утра не мочитесь или после исследования почек выпейте 0,5–1 литр воды и дождитесь наполнения."
    },
    {
        "id": 3,
        "name": "УЗИ вен нижних конечностей",
        "description": "Исследование глубоких и поверхностных вен нижних конечностей.\nПоказания: отёки, тяжесть в ногах, варикоз, судороги, подозрение на тромбоз.",
        "price": "2000 руб.",
        "preparation": ""
    },
    {
        "id": 4,
        "name": "УЗИ сосудов шеи (УЗДГ)",
        "description": "Ультразвуковая допплерография сосудов шеи.\nВходят: сонные артерии, позвоночные артерии.\nПоказания: головные боли, головокружения, шум в ушах, повышенное давление.",
        "price": "2000 руб.",
        "preparation": ""
    },
    {
        "id": 5,
        "name": "УЗИ щитовидной железы",
        "description": "Исследование щитовидной железы и регионарных лимфоузлов.\nПоказания: ощущение комка в горле, изменение веса, нервозность, подозрение на узлы.",
        "price": "2000 руб.",
        "preparation": ""
    },
    {
        "id": 6,
        "name": "УЗИ лимфатических узлов",
        "description": "Исследование лимфатических узлов различных групп.\nПоказания: увеличение, болезненность, уплотнение лимфоузлов.",
        "price": "1500 руб.",
        "preparation": ""
    },
    {
        "id": 7,
        "name": "УЗИ молочных желез",
        "description": "Исследование молочных желез и регионарных лимфоузлов.\nПоказания: боли, уплотнения, выделения из сосков, контроль после маммографии.\nОптимально проводить на 5–10 день цикла.",
        "price": "2000 руб.",
        "preparation": ""
    },
    {
        "id": 8,
        "name": "УЗИ мягких тканей",
        "description": "Исследование мягких тканей.\nВходят: кожа, подкожная клетчатка, мышцы, связки.\nПоказания: подкожные образования, травмы, гематомы.",
        "price": "1000 руб.",
        "preparation": ""
    },
    {
        "id": 9,
        "name": "УЗИ слюнных желез",
        "description": "Исследование слюнных желез.\nПоказания: припухлость, болезненность, сухость во рту, подозрение на камни.",
        "price": "1500 руб.",
        "preparation": ""
    },
    {
        "id": 10,
        "name": "УЗИ гинекологическое",
        "description": "Исследование органов малого таза у женщин.\nВходят: матка, яичники, маточные трубы, шейка матки.\nПоказания: боли внизу живота, нарушения цикла, подозрение на кисты, миомы.\nОптимально на 5–7 день цикла.",
        "price": "2000 руб.",
        "preparation": ""
    },
    {
        "id": 11,
        "name": "ТРУЗИ предстательной железы + почки + мочевой пузырь",
        "description": "Трансректальное УЗИ предстательной железы, почек и мочевого пузыря.\nПоказания: нарушения мочеиспускания, боли в промежности, подозрение на аденому.\nПрофилактика для мужчин после 40 лет.",
        "price": "2000 руб.",
        "preparation": "За 2–3 дня: исключите продукты, усиливающие газообразование — бобовые, капусту, свежий хлеб, газировку.\n\nВ день исследования: натощак, не ешьте и не пейте с утра."
    },
    {
        "id": 12,
        "name": "УЗИ мошонки",
        "description": "Исследование органов мошонки.\nВходят: яички, придатки, семенные канатики.\nПоказания: боли, отёк, уплотнения, травмы, варикоцеле.",
        "price": "1500 руб.",
        "preparation": ""
    },
    {
        "id": 13,
        "name": "УЗИ сердца (Эхокардиография)",
        "description": "УЗИ сердца.\nВходят: размеры камер, состояние клапанов, сократимость миокарда.\nПоказания: одышка, боли в груди, перебои, шумы в сердце, гипертония.",
        "price": "2000 руб.",
        "preparation": ""
    },
]

FAQ = [
    {"question": "Это безопасно? Как часто можно делать УЗИ?", "answer": "УЗИ — безопасный метод, основанный на ультразвуковых волнах. Лучевой нагрузки нет. Можно проходить так часто, как необходимо."},
    {"question": "Можно ли делать УЗИ при беременности?", "answer": "Да, УЗИ при беременности безопасно."},
    {"question": "Нужно ли направление от врача?", "answer": "Направление не обязательно. Можно прийти по собственному желанию."},
    {"question": "Выдаёте ли вы заключение на руки?", "answer": "Да, после исследования вы сразу получаете заключение на руки."},
    {"question": "Сколько длится исследование?", "answer": "Обычно 10–20 минут, в зависимости от вида УЗИ."},
    {"question": "Можно ли прийти без записи?", "answer": "Да, мы работаем в формате живой очереди."},
    {"question": "Делаете ли вы УЗИ детям?", "answer": "Нет, только взрослых от 18 лет"},
    {"question": "Какие способы оплаты?", "answer": "Оплата наличными или переводом. Уточняйте при визите."},
]

CONTACTS = {
    "address": "Усолье-Сибирское, проезд Фестивальный, 9, кабинет 312",
    "work_hours": "пн–пт с 9:00 до 13:00",
    "phone": "+7 952 613-92-71",
    "profile_link": "https://max.ru/u/f9LHodD0cOIVlZ5OVy41KdeJONNGnOzhBHJUbNBu7Onv-Vy6HI07Y0-Z6DQ",
}

# ==================== ФУНКЦИИ ====================

def auth_value() -> str:
    if USE_BEARER and not TOKEN.lower().startswith("bearer "):
        return f"Bearer {TOKEN}"
    return TOKEN

def api_headers():
    return {
        "Authorization": auth_value(),
        "Content-Type": "application/json",
    }

def make_button(text, payload=None, url=None, link=False):
    """Создание кнопки"""
    if link:
        return {"type": "link", "text": text, "url": url}
    return {"type": "callback", "text": text, "payload": payload}

def main_keyboard():
    """Главное меню с кнопками"""
    return [
        [make_button("🩺 Виды УЗИ и цены", "menu_services")],
        [make_button("❓ Вопросы и ответы", "menu_faq")],
        [make_button("📅 Запланировать визит", "menu_plan")],
        [make_button("🔔 Мои напоминания", "menu_reminders")],
        [make_button("📍 Контакты и график", "menu_contacts")],
    ]

def back_keyboard(payload="menu_main"):
    """Кнопка назад"""
    return [[make_button("← Назад", payload)]]

def send_max_message(user_id, chat_id, recipient_chat_type, text, buttons=None):
    """Отправка сообщения через MAX API."""
    url = f"{MAX_API}/messages"
    params = {}
    
    ct = (recipient_chat_type or "").strip().lower()
    
    if ct in ("chat", "channel") and chat_id is not None:
        params["chat_id"] = int(chat_id)
    elif user_id is not None:
        params["user_id"] = int(user_id)
    elif chat_id is not None:
        params["chat_id"] = int(chat_id)
    else:
        logger.warning("Нет user_id и chat_id для отправки")
        return False
    
    payload = {"text": text}
    
    if buttons:
        payload["attachments"] = [{
            "type": "inline_keyboard",
            "payload": {"buttons": buttons}
        }]
    
    try:
        r = requests.post(url, headers=api_headers(), params=params, json=payload, timeout=15)
        if r.ok:
            logger.info(f"✅ Сообщение отправлено")
            return True
        else:
            logger.error(f"❌ Ошибка: {r.status_code} {r.text[:200]}")
            return False
    except Exception as e:
        logger.exception(f"Ошибка сети: {e}")
        return False

# ==================== ОБРАБОТКА КОМАНД ====================

def process_menu_services(user_id, chat_id, chat_type):
    """Показать список услуг"""
    buttons = []
    for s in SERVICES:
        buttons.append([make_button(s["name"], f"service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])
    
    send_max_message(
        user_id, chat_id, chat_type,
        "Выберите исследование:",
        buttons
    )

def process_service_detail(user_id, chat_id, chat_type, service_id):
    """Показать детали услуги"""
    s = next((x for x in SERVICES if x["id"] == service_id), None)
    if not s:
        send_max_message(user_id, chat_id, chat_type, "❌ Исследование не найдено.")
        return
    
    text = f"🩺 {s['name']}\n\n"
    if s["description"]:
        text += f"ℹ️ {s['description']}\n\n"
    text += f"💰 Цена: {s['price']}\n\n"
    if s["preparation"]:
        text += f"📋 Подготовка:\n{s['preparation']}"
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        back_keyboard("menu_services")
    )

def process_menu_faq(user_id, chat_id, chat_type):
    """Показать FAQ"""
    buttons = []
    for i, f in enumerate(FAQ):
        question = f["question"][:50] + "..." if len(f["question"]) > 50 else f["question"]
        buttons.append([make_button(question, f"faq_{i}")])
    buttons.append([make_button("← Назад", "menu_main")])
    
    send_max_message(
        user_id, chat_id, chat_type,
        "❓ Частые вопросы:",
        buttons
    )

def process_faq_answer(user_id, chat_id, chat_type, index):
    """Показать ответ на FAQ"""
    if not 0 <= index < len(FAQ):
        send_max_message(user_id, chat_id, chat_type, "❌ Вопрос не найден.")
        return
    
    f = FAQ[index]
    text = f"❓ {f['question']}\n\n{f['answer']}"
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        back_keyboard("menu_faq")
    )

def process_menu_plan(user_id, chat_id, chat_type):
    """Показать услуги для планирования"""
    buttons = []
    for s in SERVICES:
        buttons.append([make_button(s["name"], f"plan_service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])
    
    send_max_message(
        user_id, chat_id, chat_type,
        "Выберите исследование для напоминания:",
        buttons
    )

def process_plan_periods(user_id, chat_id, chat_type, service_id):
    """Показать выбор периода"""
    buttons = [
        [make_button("📅 1 месяц", f"period_{service_id}_1")],
        [make_button("📅 3 месяца", f"period_{service_id}_3")],
        [make_button("📅 6 месяцев", f"period_{service_id}_6")],
        [make_button("📅 12 месяцев", f"period_{service_id}_12")],
        [make_button("← Назад", "menu_plan")],
    ]
    
    send_max_message(
        user_id, chat_id, chat_type,
        "Через сколько напомнить?",
        buttons
    )

def process_save_reminder(user_id, chat_id, chat_type, service_id, period):
    """Сохранить напоминание"""
    months = int(period)
    remind_date = (datetime.now() + timedelta(days=months * 30)).strftime("%d.%m.%Y")
    
    s = next((x for x in SERVICES if x["id"] == service_id), None)
    name = s["name"] if s else "Исследование"
    
    # Сохраняем в базу данных
    save_reminder_to_db(user_id, name, remind_date)
    
    text = (
        f"✅ Запланировано!\n\n"
        f"📋 Исследование: {name}\n"
        f"📅 Напомню: {remind_date}\n\n"
        f"🔔 За день до визита пришлю напоминание."
    )
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        main_keyboard()
    )

def process_menu_reminders(user_id, chat_id, chat_type):
    """Показать напоминания"""
    user_reminders = get_reminders_from_db(user_id)
    
    if not user_reminders:
        send_max_message(
            user_id, chat_id, chat_type,
            "📭 У вас нет активных напоминаний.\n\n"
            "Запланируйте визит в разделе '📅 Запланировать визит'.",
            main_keyboard()
        )
        return
    
    text = "🔔 Ваши напоминания:\n\n"
    for i, r in enumerate(user_reminders, 1):
        status = "✅ Отправлено" if r["is_sent"] else "⏳ Ожидает"
        text += f"{i}. {r['service_name']}\n"
        text += f"   📅 Дата: {r['remind_date']}\n"
        text += f"   ⏰ Создано: {r['created_at']}\n"
        text += f"   📌 Статус: {status}\n\n"
    
    # Добавляем кнопки
    buttons = []
    
    # Кнопка для проверки отправки напоминания
    buttons.append([make_button("🔔 Отправить тестовое напоминание", "test_reminder")])
    
    # Кнопка для удаления всех напоминаний
    buttons.append([make_button("🗑 Удалить все напоминания", "clear_reminders")])
    
    buttons.append([make_button("← Назад", "menu_main")])
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        buttons
    )

def process_test_reminder(user_id, chat_id, chat_type):
    """Отправить тестовое напоминание"""
    user_reminders = get_reminders_from_db(user_id)
    
    if not user_reminders:
        send_max_message(
            user_id, chat_id, chat_type,
            "📭 У вас нет напоминаний для проверки.",
            main_keyboard()
        )
        return
    
    # Берем первое напоминание
    r = user_reminders[0]
    
    text = (
        f"🔔 НАПОМИНАНИЕ!\n\n"
        f"📋 Исследование: {r['service_name']}\n"
        f"📅 Дата: {r['remind_date']}\n\n"
        f"📍 Адрес: {CONTACTS['address']}\n"
        f"🕒 Часы работы: {CONTACTS['work_hours']}\n"
        f"📞 Телефон: {CONTACTS['phone']}\n\n"
        f"Ждём вас!"
    )
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        main_keyboard()
    )

def process_clear_reminders(user_id, chat_id, chat_type):
    """Удалить все напоминания"""
    deleted = delete_all_reminders_from_db(user_id)
    
    if deleted > 0:
        send_max_message(
            user_id, chat_id, chat_type,
            f"✅ Удалено напоминаний: {deleted}",
            main_keyboard()
        )
    else:
        send_max_message(
            user_id, chat_id, chat_type,
            "📭 У вас нет напоминаний.",
            main_keyboard()
        )

def process_menu_contacts(user_id, chat_id, chat_type):
    """Показать контакты"""
    text = (
        f"📍 Адрес: {CONTACTS['address']}\n\n"
        f"🕒 Часы работы: {CONTACTS['work_hours']}\n\n"
        f"📞 Телефон: {CONTACTS['phone']}"
    )
    
    buttons = [
        [make_button("👨‍⚕️ Написать доктору", url=CONTACTS["profile_link"], link=True)],
        [make_button("← Назад", "menu_main")],
    ]
    
    send_max_message(
        user_id, chat_id, chat_type,
        text,
        buttons
    )

# ==================== ФОНОВАЯ ПРОВЕРКА НАПОМИНАНИЙ ====================

def check_reminders_loop():
    """Фоновая проверка напоминаний каждый час"""
    while True:
        try:
            # Получаем напоминания на завтра
            tomorrow_reminders = get_unsent_reminders_for_tomorrow()
            
            for reminder in tomorrow_reminders:
                # Отправляем напоминание
                text = (
                    f"🔔 НАПОМИНАНИЕ!\n\n"
                    f"📋 Исследование: {reminder['service_name']}\n"
                    f"📅 Завтра: {reminder['remind_date']}\n\n"
                    f"📍 Адрес: {CONTACTS['address']}\n"
                    f"🕒 Часы работы: {CONTACTS['work_hours']}\n"
                    f"📞 Телефон: {CONTACTS['phone']}\n\n"
                    f"Ждём вас!"
                )
                
                success = send_max_message(
                    user_id=reminder['user_id'],
                    chat_id=None,
                    recipient_chat_type="dialog",
                    text=text
                )
                
                if success:
                    # Отмечаем как отправленное
                    mark_reminder_as_sent(reminder['id'])
                    logger.info(f"🔔 Отправлено напоминание для user_id={reminder['user_id']}")
                
                # Небольшая пауза между отправками
                time.sleep(1)
            
            # Проверяем каждый час
            time.sleep(3600)
            
        except Exception as e:
            logger.error(f"Ошибка в check_reminders_loop: {e}")
            time.sleep(60)

def process_callback(user_id, chat_id, chat_type, payload):
    """Обработка нажатий на кнопки"""
    logger.info(f"🔘 Callback: {payload}, user_id={user_id}, chat_id={chat_id}, chat_type={chat_type}")
    
    if payload == "menu_main":
        send_max_message(
            user_id, chat_id, chat_type,
            "Главное меню:",
            main_keyboard()
        )
    
    elif payload == "menu_services":
        process_menu_services(user_id, chat_id, chat_type)
    
    elif payload.startswith("service_"):
        service_id = int(payload.split("_")[1])
        process_service_detail(user_id, chat_id, chat_type, service_id)
    
    elif payload == "menu_faq":
        process_menu_faq(user_id, chat_id, chat_type)
    
    elif payload.startswith("faq_"):
        index = int(payload.split("_")[1])
        process_faq_answer(user_id, chat_id, chat_type, index)
    
    elif payload == "menu_plan":
        process_menu_plan(user_id, chat_id, chat_type)
    
    elif payload.startswith("plan_service_"):
        service_id = int(payload.split("_")[2])
        process_plan_periods(user_id, chat_id, chat_type, service_id)
    
    elif payload.startswith("period_"):
        parts = payload.split("_")
        service_id = int(parts[1])
        period = parts[2]
        process_save_reminder(user_id, chat_id, chat_type, service_id, period)
    
    elif payload == "menu_reminders":
        process_menu_reminders(user_id, chat_id, chat_type)
    
    elif payload == "test_reminder":
        process_test_reminder(user_id, chat_id, chat_type)
    
    elif payload == "clear_reminders":
        process_clear_reminders(user_id, chat_id, chat_type)
    
    elif payload == "menu_contacts":
        process_menu_contacts(user_id, chat_id, chat_type)

# ==================== ВЕБХУК ====================

@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200
    
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        logger.warning("Тело не JSON")
        return jsonify({"ok": True}), 200
    
    update_type = data.get("update_type")
    logger.info(f"📥 Получен update: {update_type}")
    
    # Обработка нажатия "Начать"
    if update_type == "bot_started":
        chat_id = data.get("chat_id")
        user = data.get("user", {})
        user_id = user.get("user_id")
        
        logger.info(f"🔄 Пользователь {user_id} нажал 'Начать'")
        
        send_max_message(
            user_id=user_id,
            chat_id=chat_id,
            recipient_chat_type="dialog",
            text="👋 Здравствуйте!\n\n"
                 "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
                 "Помогу узнать цены, подготовку и напомню о визите.\n\n"
                 "Выберите действие:",
            buttons=main_keyboard()
        )
        return jsonify({"ok": True}), 200
    
    # Обработка обычных сообщений
    if update_type == "message_created":
        msg = data.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})
        body = msg.get("body", {})
        
        chat_id = recipient.get("chat_id")
        chat_type = recipient.get("chat_type")
        user_id = sender.get("user_id")
        text = (body.get("text") or "").strip()
        
        logger.info(f"📩 Сообщение от {user_id}: '{text}'")
        
        if text.startswith("/start"):
            send_max_message(
                user_id=user_id,
                chat_id=chat_id,
                recipient_chat_type=chat_type,
                text="👋 Здравствуйте!\n\n"
                     "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
                     "Помогу узнать цены, подготовку и напомню о визите.\n\n"
                     "Выберите действие:",
                buttons=main_keyboard()
            )
        else:
            send_max_message(
                user_id=user_id,
                chat_id=chat_id,
                recipient_chat_type=chat_type,
                text="Главное меню:",
                buttons=main_keyboard()
            )
        
        return jsonify({"ok": True}), 200
    
    # Обработка нажатий на кнопки
    if update_type == "message_callback":
        cb = data.get("callback", {})
        payload = cb.get("payload", "")
        callback_id = cb.get("callback_id")
        
        # Пробуем разные варианты получения данных
        msg = cb.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})
        
        chat_id = recipient.get("chat_id")
        chat_type = recipient.get("chat_type")
        user_id = sender.get("user_id")
        
        # Вариант 2: из верхнего уровня
        if not user_id:
            user_id = data.get("user_id")
        if not chat_id:
            chat_id = data.get("chat_id")
        if not chat_type:
            chat_type = data.get("chat_type", "dialog")
        
        # Вариант 3: из callback.user
        if not user_id and cb.get("user"):
            user_id = cb["user"].get("user_id")
        
        logger.info(f"Callback data: user_id={user_id}, chat_id={chat_id}, chat_type={chat_type}, payload={payload}")
        
        # Отвечаем на callback (снимаем часики)
        if callback_id:
            try:
                requests.post(
                    f"{MAX_API}/answers",
                    headers=api_headers(),
                    params={"callback_id": callback_id},
                    json={"notification": "Готово"},
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Ошибка answers: {e}")
        
        # Обрабатываем payload
        if user_id or chat_id:
            process_callback(user_id, chat_id, chat_type, payload)
        else:
            logger.error("Не удалось определить user_id или chat_id")
        
        return jsonify({"ok": True}), 200
    
    return jsonify({"ok": True}), 200

# ==================== ЗДОРОВЬЕ ====================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/send_news", methods=["POST"])
def send_news():
    """Рассылка новостей всем пользователям MAX."""
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"ok": False, "error": "Нет текста"}), 400

    text = data["text"]

    # Получаем всех пользователей из базы
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM reminders")
    users = cursor.fetchall()
    conn.close()

    sent = 0
    for user in users:
        try:
            success = send_max_message(
                user_id=user[0],
                chat_id=None,
                recipient_chat_type="dialog",
                text=text
            )
            if success:
                sent += 1
        except:
            pass

    return jsonify({"ok": True, "sent": sent}), 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": "UZI Bot"}), 200

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Задайте MAX_BOT_TOKEN")
    
    # Инициализируем базу данных
    init_db()
    
    # Запускаем фоновую проверку напоминаний
    reminder_thread = threading.Thread(target=check_reminders_loop, daemon=True)
    reminder_thread.start()
    logger.info("✅ Фоновая проверка напоминаний запущена")
    
    port = int(os.environ.get("PORT", "3000"))
    logger.info(f"🚀 Бот запущен на порту {port}")
    logger.info(f"📡 Webhook URL: https://ваш-домен/webhook")
    app.run(host="0.0.0.0", port=port)
