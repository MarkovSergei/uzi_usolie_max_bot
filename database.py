import sqlite3
import os

DB_PATH = os.path.join(os.getenv("DATA_PATH", "/app/data"), "bot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now', '+8 hours')),
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price TEXT DEFAULT '',
            preparation TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            remind_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', '+8 hours')),
            is_sent INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            sent_at TEXT DEFAULT (datetime('now', '+8 hours')),
            recipients INTEGER DEFAULT 0
        )
    """)

    defaults = {
        "address": "Усолье-Сибирское, проезд Фестивальный, 9, кабинет 312",
        "work_hours": "пн–пт с 9:00 до 13:00",
        "phone": "+7 952 613-92-71",
        "map_link": "https://yandex.ru/maps/?text=Усолье-Сибирское, проезд Фестивальный, 9"
    }

    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    conn.commit()
    conn.close()
