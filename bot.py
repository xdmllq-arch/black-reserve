import os
import asyncio
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv


# =========================
# CONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8336765971
DB_NAME = "black_reserve.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# DATABASE
# =========================

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
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    }

    if "username" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN username TEXT"
        )

    if "first_name" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN first_name TEXT"
        )

    if "balance" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0"
        )

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
        "FROM users "
        "ORDER BY rowid DESC"
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
        "UPDATE users "
        "SET balance = balance + ? "
        "WHERE user_id = ?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


# =========================
# MAIN MENU
# =========================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📍 Бишкек")
        ],
        [
            KeyboardButton(text="💰 Баланс"),
            KeyboardButton(text="💳 Пополнить")
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⭐ Отзывы")
        ],
        [
            KeyboardButton(text="📞 Поддержка")
        ]
    ],
    resize_keyboard=True
)


# =========================
# BISHKEK MENU
# =========================

bishkek_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Ленинский район"),
            KeyboardButton(text="Октябрьский район")
        ],
        [
            KeyboardButton(text="Первомайский район"),
            KeyboardButton(text="Свердловский район")
        ],
        [
            KeyboardButton(text="🔙 Главное меню")
        ]
    ],
    resize_keyboard=True
)


# =========================
# DISTRICT MENU
# =========================

district_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛍️ Позиции")
        ],
        [
            KeyboardButton(text="🔙 Районы Бишкек")
        ],
        [
            KeyboardButton(text="🏠 Главное меню")
        ]
    ],
    resize_keyboard=True
)


# =========================
# ADMIN MENU
# =========================

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Пользователи"),
            KeyboardButton(text="💰 Балансы")
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⚙️ Настройки")
        ],
        [
            KeyboardButton(text="🔙 Главное меню")
        ]
    ],
    resize_keyboard=True
)


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать!",
        reply_markup=main_menu
    )


# =========================
# ADMIN
# =========================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещён.")
        return

    await message.answer(
        "⚙️ BLACK RESERVE — ADMIN\n\n"
        "Панель управления:",
        reply_markup=admin_menu
    )


# =========================
# MESSAGE HANDLER
# =========================

@dp.message()
async def handler(message: Message):
    uid = message.from_user.id
    text = message.text or ""

    # -------------------------
    # BISHKEK
    # -------------------------

    if text == "📍 Бишкек":
        await message.answer(
            "📍 БИШКЕК\n\n"
            "Выберите район:",
            reply_markup=bishkek_menu
        )
        return

    # -------------------------
    # DISTRICTS
    # -------------------------

    districts = {
        "Ленинский район",
        "Октябрьский район",
        "Первомайский район",
        "Свердловский район"
    }

    if text in districts:
        await message.answer(
            "📍 БИШКЕК\n"
            "Район: " + text + "\n\n"
            "Выберите действие:",
            reply_markup=district_menu
        )
        return

    # -------------------------
    # POSITIONS
    # -------------------------

    if text == "🛍️ Позиции":
        await message.answer(
            "🛍️ ПОЗИЦИИ\n\n"
            "Позиции этого района скоро будут добавлены."
        )
        return

    # -------------------------
    # BACK TO DISTRICTS
    # -------------------------

    if text == "🔙 Районы Бишкек":
        await message.answer(
            "📍 БИШКЕК\n\n"
            "Выберите район:",
            reply_markup=bishkek_menu
        )
        return

    # -------------------------
    # USERS
    # -------------------------

    if text == "👤 Пользователи":
        if uid != ADMIN_ID:
            return

        users = get_users()

        output = "👤 ПОЛЬЗОВАТЕЛИ\n\n"
        output += "Всего: " + str(len(users)) + "\n\n"

        if not users:
            output += "Пользователей пока нет."
        else:
            for number, user in enumerate(users, 1):
                user_id = user[0]
                username = user[1]
                first_name = user[2]
                balance = user[3]

                name = first_name or "Без имени"

                if username:
                    name += " (@" + username + ")"

                output += (
                    str(number) + ". " + name + "\n"
                    "🆔 " + str(user_id) + "\n"
                    "💰 $" + format(float(balance), ".2f") + "\n\n"
                )

        await message.answer(output)
        return

    # -------------------------
    # BALANCES ADMIN
    # -------------------------

    if text == "💰
