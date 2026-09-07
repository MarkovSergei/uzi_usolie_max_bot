import asyncio
import aiosqlite
import os
import requests
import urllib3
from datetime import datetime, timedelta
import time

# Отключаем предупреждения SSL (для MAX API)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== КОНФИГУРАЦИЯ ====================

API_URL = "https://platform-api2.max.ru"
TOKEN = os.getenv("MAX_BOT_TOKEN", "")
if not TOKEN:
    print("⚠️ ВНИМАНИЕ: MAX_BOT_TOKEN не установлен!")

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

# Путь к БД на bothost.ru
DATA_PATH = os.getenv("DATA_PATH", "/app/data")
DB_PATH = os.path.join(DATA_PATH, "bot.db")

# Создаем папку для БД, если её нет
os.makedirs(DATA_PATH, exist_ok=True)

# ==================== ДАННЫЕ ====================

SERVICES = [
    {
        "id": 1,
        "name": "УЗИ органов брюшной полости",
        "description": (
            "Комплексное исследование органов брюшной полости и забрюшинного пространства.\n"
            "Входят: печень, желчный пузырь, поджелудочная железа, селезенка, почки, мочевой пузырь.\n\n"
            "Показания: боли в животе, тяжесть после еды, тошнота, горечь во рту, "
            "подозрение на камни, контроль хронических заболеваний."
        ),
        "price": "2000 руб.",
        "preparation": (
            "За 2–3 дня: исключите продукты, вызывающие вздутие — свежий хлеб, бобовые, "
            "капусту, газированные напитки, сырые овощи и фрукты.\n"
            "При склонности к метеоризму можно принимать эспумизан.\n\n"
            "В день исследования: приходите натощак. Утром не есть и не пить."
        ),
    },
    {
        "id": 2,
        "name": "УЗИ почек и мочевого пузыря",
        "description": (
            "Исследование почек и мочевого пузыря.\n"
            "Показания: боли в пояснице, отёки, изменения в анализах мочи, "
            "подозрение на камни, кисты, новообразования."
        ),
        "price": "1500 руб.",
        "preparation": (
            "За 2–3 дня: исключите газообразующие продукты — бобовые, капусту, газировку, свежую выпечку.\n\n"
            "В день исследования: натощак — не пить и не есть.\n"
            "Если нужно посмотреть мочевой пузырь: с утра не мочитесь или после исследования почек "
            "выпейте 0,5–1 литр воды и дождитесь наполнения."
        ),
    },
    {
        "id": 3,
        "name": "УЗИ вен нижних конечностей",
        "description": (
            "Исследование глубоких и поверхностных вен нижних конечностей.\n"
            "Показания: отёки, тяжесть в ногах, варикоз, судороги, подозрение на тромбоз."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
    {
        "id": 4,
        "name": "УЗИ сосудов шеи (УЗДГ)",
        "description": (
            "Ультразвуковая допплерография сосудов шеи.\n"
            "Входят: сонные артерии, позвоночные артерии.\n"
            "Показания: головные боли, головокружения, шум в ушах, повышенное давление."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
    {
        "id": 5,
        "name": "УЗИ щитовидной железы",
        "description": (
            "Исследование щитовидной железы и регионарных лимфоузлов.\n"
            "Показания: ощущение комка в горле, изменение веса, нервозность, подозрение на узлы."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
    {
        "id": 6,
        "name": "УЗИ лимфатических узлов",
        "description": (
            "Исследование лимфатических узлов различных групп.\n"
            "Показания: увеличение, болезненность, уплотнение лимфоузлов."
        ),
        "price": "1500 руб.",
        "preparation": "",
    },
    {
        "id": 7,
        "name": "УЗИ молочных желез",
        "description": (
            "Исследование молочных желез и регионарных лимфоузлов.\n"
            "Показания: боли, уплотнения, выделения из сосков, контроль после маммографии.\n"
            "Оптимально проводить на 5–10 день цикла."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
    {
        "id": 8,
        "name": "УЗИ мягких тканей",
        "description": (
            "Исследование мягких тканей.\n"
            "Входят: кожа, подкожная клетчатка, мышцы, связки.\n"
            "Показания: подкожные образования, травмы, гематомы."
        ),
        "price": "1000 руб.",
        "preparation": "",
    },
    {
        "id": 9,
        "name": "УЗИ слюнных желез",
        "description": (
            "Исследование слюнных желез.\n"
            "Показания: припухлость, болезненность, сухость во рту, подозрение на камни."
        ),
        "price": "1500 руб.",
        "preparation": "",
    },
    {
        "id": 10,
        "name": "УЗИ гинекологическое",
        "description": (
            "Исследование органов малого таза у женщин.\n"
            "Входят: матка, яичники, маточные трубы, шейка матки.\n"
            "Показания: боли внизу живота, нарушения цикла, подозрение на кисты, миомы.\n"
            "Оптимально на 5–7 день цикла."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
    {
        "id": 11,
        "name": "ТРУЗИ предстательной железы + почки + мочевой пузырь",
        "description": (
            "Трансректальное УЗИ предстательной железы, почек и мочевого пузыря.\n"
            "Показания: нарушения мочеиспускания, боли в промежности, подозрение на аденому.\n"
            "Профилактика для мужчин после 40 лет."
        ),
        "price": "2000 руб.",
        "preparation": (
            "За 2–3 дня: исключите продукты, усиливающие газообразование — бобовые, капусту, свежий хлеб, газировку.\n\n"
            "В день исследования: натощак, не ешьте и не пейте с утра."
        ),
    },
    {
        "id": 12,
        "name": "УЗИ мошонки",
        "description": (
            "Исследование органов мошонки.\n"
            "Входят: яички, придатки, семенные канатики.\n"
            "Показания: боли, отёк, уплотнения, травмы, варикоцеле."
        ),
        "price": "1500 руб.",
        "preparation": "",
    },
    {
        "id": 13,
        "name": "Эхокардиография (УЗИ сердца)",
        "description": (
            "УЗИ сердца.\n"
            "Входят: размеры камер, состояние клапанов, сократимость миокарда.\n"
            "Показания: одышка, боли в груди, перебои, шумы в сердце, гипертония."
        ),
        "price": "2000 руб.",
        "preparation": "",
    },
]

FAQ = [
    {
        "question": "Это безопасно? Как часто можно делать УЗИ?",
        "answer": "УЗИ — безопасный метод, основанный на ультразвуковых волнах. Лучевой нагрузки нет. Можно проходить так часто, как необходимо."
    },
    {
        "question": "Можно ли делать УЗИ при беременности?",
        "answer": "Да, УЗИ при беременности безопасно и необходимо для контроля развития плода."
    },
    {
        "question": "Нужно ли направление от врача?",
        "answer": "Направление не обязательно. Можно прийти по собственному желанию."
    },
    {
        "question": "Выдаёте ли вы заключение на руки?",
        "answer": "Да, после исследования вы сразу получаете заключение на руки."
    },
    {
        "question": "Сколько длится исследование?",
        "answer": "Обычно 10–20 минут, в зависимости от вида УЗИ."
    },
    {
        "question": "Можно ли прийти без записи?",
        "answer": "Да, мы работаем в формате живой очереди."
    },
    {
        "question": "Делаете ли вы УЗИ детям?",
        "answer": "Да, УЗИ детям проводится. Метод безопасен с рождения."
    },
    {
        "question": "Какие способы оплаты?",
        "answer": "Оплата наличными или переводом. Уточняйте при визите."
    },
]

CONTACTS = {
    "address": "Усолье-Сибирское, проезд Фестивальный, 9, кабинет 312",
    "work_hours": "пн–пт с 9:00 до 13:00",
    "phone": "+7 952 613-92-71",
    "map_link": "https://yandex.ru/maps/?text=Усолье-Сибирское, проезд Фестивальный, 9",
    "doctor_link": "https://t.me/MarkovSerge",
}

# ==================== БАЗА ДАННЫХ (aiosqlite) ====================

async def init_db():
    """Инициализация базы данных (асинхронная)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    service_id INTEGER NOT NULL,
                    remind_date TEXT NOT NULL,
                    is_sent INTEGER DEFAULT 0
                )
            """)
            # Добавляем индексы для быстрого поиска
            await db.execute("CREATE INDEX IF NOT EXISTS idx_remind_date ON reminders(remind_date)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_id ON reminders(chat_id)")
            await db.commit()
            print(f"✅ База данных инициализирована: {DB_PATH}")
            return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

# ==================== ОТПРАВКА СООБЩЕНИЙ ====================

def send_message(chat_id, text, buttons=None, retries=3):
    """Отправка сообщения с повторными попытками"""
    url = f"{API_URL}/messages"
    payload = {"chat_id": chat_id, "text": text}
    
    if buttons:
        payload["attachments"] = [{
            "type": "inline_keyboard",
            "payload": {"buttons": buttons}
        }]
    
    for attempt in range(retries):
        try:
            response = requests.post(
                url, 
                json=payload, 
                headers=HEADERS, 
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                return True
            
            print(f"⚠️ Ошибка отправки (попытка {attempt+1}): {response.status_code} - {response.text}")
            
            if response.status_code == 401:
                print("❌ Ошибка авторизации! Проверьте MAX_BOT_TOKEN")
                return False
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Таймаут отправки (попытка {attempt+1})")
        except Exception as e:
            print(f"⚠️ Ошибка отправки (попытка {attempt+1}): {e}")
        
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    
    return False

def make_button(text, payload=None, url=None, link=False):
    """Создание кнопки"""
    if link:
        return {"type": "link", "text": text, "url": url}
    return {"type": "callback", "text": text, "payload": payload}

def main_keyboard():
    """Главное меню"""
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

# ==================== ОБРАБОТКА ОБНОВЛЕНИЙ ====================

def process_update(update):
    """Обработка входящего обновления"""
    update_type = update.get("update_type")
    chat_id = update.get("chat_id")

    if not chat_id:
        return

    if update_type == "bot_started":
        send_message(
            chat_id,
            "👋 Здравствуйте!\n\n"
            "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
            "Помогу узнать цены, подготовку и напомню о визите.\n\n"
            "Выберите действие:",
            main_keyboard()
        )
        return

    if update_type == "message_created":
        message = update.get("message", {})
        body = message.get("body", {})
        text = body.get("text", "")
        
        if text == "/start":
            send_message(
                chat_id,
                "👋 Здравствуйте!\n\n"
                "Я бот кабинета УЗИ Маркова Сергея Борисовича.\n"
                "Помогу узнать цены, подготовку и напомню о визите.\n\n"
                "Выберите действие:",
                main_keyboard()
            )
        elif text == "/help":
            send_message(
                chat_id,
                "📖 Помощь:\n\n"
                "• Используйте кнопки для навигации\n"
                "• /start - главное меню\n"
                "• /help - эта справка",
                main_keyboard()
            )
        return

    if update_type == "message_callback":
        payload = update.get("payload", "")
        if payload:
            process_callback(chat_id, payload)

def process_callback(chat_id, payload):
    """Обработка callback-запросов"""
    
    if payload == "menu_main":
        send_message(chat_id, "Главное меню:", main_keyboard())
    elif payload == "menu_services":
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
        # Запускаем асинхронную операцию в фоне
        asyncio.create_task(save_reminder(chat_id, int(payload.split("_")[1]), payload.split("_")[2]))
    elif payload.startswith("upd_"):
        asyncio.create_task(update_reminder(chat_id, int(payload.split("_")[1]), payload.split("_")[2]))
    elif payload == "menu_reminders":
        asyncio.create_task(show_reminders(chat_id))
    elif payload == "menu_contacts":
        show_contacts(chat_id)

# ==================== РАЗДЕЛЫ МЕНЮ ====================

def show_services(chat_id):
    """Показать список услуг"""
    buttons = []
    for s in SERVICES:
        buttons.append([make_button(s["name"], f"service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])
    send_message(chat_id, "Выберите исследование:", buttons)

def show_service_detail(chat_id, service_id):
    """Показать детали услуги"""
    s = next((x for x in SERVICES if x["id"] == service_id), None)
    if not s:
        send_message(chat_id, "❌ Исследование не найдено.")
        return

    text = f"🩺 {s['name']}\n\n"
    if s["description"]:
        text += f"ℹ️ {s['description']}\n\n"
    text += f"💰 Цена: {s['price']}\n\n"
    if s["preparation"]:
        text += f"📋 Подготовка:\n{s['preparation']}"

    send_message(chat_id, text, back_keyboard("menu_services"))

def show_faq(chat_id):
    """Показать список FAQ"""
    buttons = []
    for i, f in enumerate(FAQ):
        question = f["question"][:50] + "..." if len(f["question"]) > 50 else f["question"]
        buttons.append([make_button(question, f"faq_{i}")])
    buttons.append([make_button("← Назад", "menu_main")])
    send_message(chat_id, "❓ Частые вопросы:", buttons)

def show_faq_answer(chat_id, index):
    """Показать ответ на FAQ"""
    if not 0 <= index < len(FAQ):
        send_message(chat_id, "❌ Вопрос не найден.")
        return
    
    f = FAQ[index]
    text = f"❓ {f['question']}\n\n{f['answer']}"
    send_message(chat_id, text, back_keyboard("menu_faq"))

def show_plan_services(chat_id):
    """Показать услуги для планирования"""
    buttons = []
    for s in SERVICES:
        buttons.append([make_button(s["name"], f"plan_service_{s['id']}")])
    buttons.append([make_button("← Назад", "menu_main")])
    send_message(chat_id, "Выберите исследование для напоминания:", buttons)

def show_plan_periods(chat_id, service_id):
    """Показать выбор периода для напоминания"""
    buttons = [
        [make_button("📅 1 месяц", f"period_{service_id}_1")],
        [make_button("📅 3 месяца", f"period_{service_id}_3")],
        [make_button("📅 6 месяцев", f"period_{service_id}_6")],
        [make_button("📅 12 месяцев", f"period_{service_id}_12")],
        [make_button("← Назад", "menu_plan")],
    ]
    send_message(chat_id, "Через сколько напомнить?", buttons)

async def save_reminder(chat_id, service_id, period):
    """Сохранить напоминание (асинхронная)"""
    months = int(period)
    remind_date = (datetime.now() + timedelta(days=months * 30)).strftime("%d.%m.%Y")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Проверяем существующее напоминание
            cursor = await db.execute(
                "SELECT remind_date FROM reminders WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
                (str(chat_id), service_id)
            )
            existing = await cursor.fetchone()

            if existing:
                buttons = [
                    [make_button("✅ Да, обновить", f"upd_{service_id}_{remind_date}")],
                    [make_button("❌ Отмена", "menu_main")],
                ]
                send_message(
                    chat_id, 
                    f"⚠️ Уже запланировано на {existing[0]}.\nОбновить?", 
                    buttons
                )
                return

            # Сохраняем новое напоминание
            await db.execute(
                "INSERT INTO reminders (chat_id, service_id, remind_date) VALUES (?, ?, ?)",
                (str(chat_id), service_id, remind_date)
            )
            await db.commit()
            
            s = next((x for x in SERVICES if x["id"] == service_id), None)
            name = s["name"] if s else "Исследование"

            send_message(
                chat_id,
                f"✅ Запланировано!\n\n"
                f"📋 Исследование: {name}\n"
                f"📅 Напомню: {remind_date}\n\n"
                f"🔔 За день до визита пришлю напоминание.",
                main_keyboard()
            )
    except Exception as e:
        print(f"❌ Ошибка сохранения напоминания: {e}")
        send_message(chat_id, "❌ Произошла ошибка. Попробуйте позже.")

async def update_reminder(chat_id, service_id, remind_date):
    """Обновить напоминание (асинхронная)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE reminders SET remind_date = ? WHERE chat_id = ? AND service_id = ? AND is_sent = 0",
                (remind_date, str(chat_id), service_id)
            )
            await db.commit()
            send_message(
                chat_id, 
                f"✅ Дата обновлена!\n\n📅 Напомню: {remind_date}", 
                main_keyboard()
            )
    except Exception as e:
        print(f"❌ Ошибка обновления: {e}")
        send_message(chat_id, "❌ Ошибка обновления.")

async def show_reminders(chat_id):
    """Показать активные напоминания (асинхронная)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT service_id, remind_date FROM reminders WHERE chat_id = ? AND is_sent = 0 ORDER BY remind_date",
                (str(chat_id),)
            )
            reminders = await cursor.fetchall()
            
            if not reminders:
                send_message(chat_id, "📭 У вас нет активных напоминаний.", main_keyboard())
                return

            text = "📋 Ваши напоминания:\n\n"
            for r in reminders:
                s = next((x for x in SERVICES if x["id"] == r[0]), None)
                name = s["name"] if s else "Исследование"
                text += f"• {name} — {r[1]}\n"
            
            text += "\n⌛ Напоминания приходят за день до даты."
            send_message(chat_id, text, main_keyboard())
    except Exception as e:
        print(f"❌ Ошибка получения напоминаний: {e}")
        send_message(chat_id, "❌ Ошибка получения напоминаний.")

def show_contacts(chat_id):
    """Показать контакты"""
    text = (
        f"📍 Адрес: {CONTACTS['address']}\n\n"
        f"🕒 Часы работы: {CONTACTS['work_hours']}\n\n"
        f"📞 Телефон: {CONTACTS['phone']}"
    )
    buttons = [
        [make_button("🗺 Открыть на карте", url=CONTACTS["map_link"], link=True)],
        [make_button("📲 Задать вопрос врачу", url=CONTACTS["doctor_link"], link=True)],
        [make_button("← Назад", "menu_main")],
    ]
    send_message(chat_id, text, buttons)

# ==================== ПРОВЕРКА НАПОМИНАНИЙ ====================

async def reminder_checker():
    """Фоновая проверка напоминаний (каждый час)"""
    print("🔄 Запущен планировщик напоминаний")
    
    while True:
        try:
            today = datetime.now().strftime("%d.%m.%Y")
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Находим напоминания на сегодня
                cursor = await db.execute(
                    "SELECT id, chat_id, service_id FROM reminders WHERE remind_date = ? AND is_sent = 0",
                    (today,)
                )
                reminders = await cursor.fetchall()
                
                if reminders:
                    print(f"📨 Отправка {len(reminders)} напоминаний")
                    
                    for rid, chat_id, service_id in reminders:
                        s = next((x for x in SERVICES if x["id"] == service_id), None)
                        name = s["name"] if s else "исследование"
                        
                        text = (
                            f"🔔 Напоминание!\n\n"
                            f"Завтра у вас запланировано: {name}\n\n"
                            f"📍 {CONTACTS['address']}\n\n"
                            f"⏰ {CONTACTS['work_hours']}\n\n"
                            f"Ждём вас! 🌟"
                        )
                        
                        if send_message(chat_id, text):
                            # Отмечаем как отправленное
                            await db.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (rid,))
                            print(f"✅ Напоминание {rid} отправлено")
                        else:
                            print(f"❌ Не удалось отправить напоминание {rid}")
                    
                    await db.commit()
            
            # Ждем 1 час перед следующей проверкой
            await asyncio.sleep(3600)
            
        except Exception as e:
            print(f"❌ Ошибка в reminder_checker: {e}")
            await asyncio.sleep(60)

# ==================== ЗАПУСК БОТА ====================

async def run_max_bot():
    """Основная функция запуска бота"""
    print("🚀 MAX BOT STARTING...")
    
    # Инициализация базы данных
    if not await init_db():
        print("❌ Критическая ошибка: не удалось инициализировать БД")
        return
    
    # Проверка токена
    if not TOKEN:
        print("❌ Ошибка: MAX_BOT_TOKEN не установлен!")
        print("📌 Установите переменную окружения MAX_BOT_TOKEN")
        return
    
    # Проверка подключения к MAX API
    try:
        response = requests.get(
            f"{API_URL}/me", 
            headers=HEADERS, 
            timeout=10, 
            verify=False
        )
        
        if response.status_code == 200:
            print("✅ Подключение к MAX API успешно")
            try:
                data = response.json()
                print(f"🤖 Бот: {data.get('name', 'Unknown')}")
            except:
                pass
        else:
            print(f"⚠️ Ошибка подключения к MAX API: {response.status_code}")
            print(f"Ответ: {response.text}")
    except Exception as e:
        print(f"⚠️ Не удалось подключиться к MAX API: {e}")
    
    # Запускаем проверку напоминаний в фоне
    asyncio.create_task(reminder_checker())
    print("🔄 Планировщик напоминаний запущен")
    
    # Основной цикл получения обновлений
    print("📡 Начинаем polling...")
    marker = None
    error_count = 0
    
    while True:
        try:
            params = {}
            if marker:
                params["marker"] = marker
            
            response = requests.get(
                f"{API_URL}/updates", 
                headers=HEADERS, 
                params=params, 
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                marker = data.get("marker", marker)
                
                updates = data.get("updates", [])
                if updates:
                    print(f"📨 Получено {len(updates)} обновлений")
                    for update in updates:
                        process_update(update)
                
                error_count = 0
            else:
                error_count += 1
                print(f"⚠️ Ошибка polling: {response.status_code}")
                if response.status_code == 401:
                    print("❌ Ошибка авторизации! Проверьте токен.")
                    await asyncio.sleep(60)
                    continue
                    
        except requests.exceptions.Timeout:
            error_count += 1
            print(f"⏱️ Таймаут polling (ошибок: {error_count})")
        except Exception as e:
            error_count += 1
            print(f"⚠️ Ошибка polling: {e}")
        
        if error_count > 10:
            print("🛑 Слишком много ошибок, пауза 60 секунд...")
            await asyncio.sleep(60)
            error_count = 0
        
        await asyncio.sleep(2)
