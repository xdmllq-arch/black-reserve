import os
import asyncio
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8336765971
DB_NAME = "black_reserve.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db()

    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "user_id INTEGER PRIMARY KEY,"
        "username TEXT,"
        "first_name TEXT,"
        "balance REAL DEFAULT 0"
        ")"
    )

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    if "username" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN username TEXT")

    if "first_name" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT")

    if "balance" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0")

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = db()

    conn.execute(
        "INSERT INTO users "
        "(user_id, username, first_name, balance) "
        "VALUES (?, ?, ?, 0) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "username = excluded.username, "
        "first_name = excluded.first_name",
        (user_id, username, first_name)
    )

    conn.commit()
    conn.close()


def get_users():
    conn = db()

    users = conn.execute(
        "SELECT user_id, username, first_name, balance "
        "FROM users ORDER BY rowid DESC"
    ).fetchall()

    conn.close()

    return users


def get_balance(user_id):
    conn = db()

    result = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if result is None:
        return 0.0

    return float(result[0])


def change_balance(user_id, amount):
    conn = db()

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Бишкек")],
        [
            KeyboardButton(text="💰 Баланс"),
            KeyboardButton(text="💳 Пополнить")
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⭐ Отзывы")
        ],
        [KeyboardButton(text="📞 Поддержка")]
    ],
    resize_keyboard=True
)


bishkek_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Ленинский район"),
            KeyboardButton(text="Октябрьский район")
        ],
        [
            KeyboardButton(text="Первомайский район"),
            KeyboardButton(text="Свердлов
