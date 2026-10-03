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


def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, balance)
        VALUES (?, ?, ?, 0)
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def get_users():
    conn = sqlite3.connect(DB_NAME)
    users = conn.execute("""
        SELECT user_id, username, first_name, balance
        FROM users
        ORDER BY rowid DESC
    """).fetchall()
    conn.close()
    return users


def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    result = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    return result[0] if result else 0


def change_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (amount, user_id))

    conn.commit()
    conn.close()


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💰 Баланс"),
            KeyboardButton(text="💳 Пополнить"),
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⭐ Отзывы"),
        ],
        [
            KeyboardButton(text="📞 Поддержка"),
        ],
    ],
    resize_keyboard=True,
)


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Пользователи"),
            KeyboardButton(text="💰 Балансы"),
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⚙️ Настройки"),
        ],
        [
            KeyboardButton(text="🔙 Главное меню"),
        ],
    ],
    resize_keyboard=True,
)


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


@dp.message()
async def message_handler(message: Message):

    user_id = message.from_user.id

    if message.text == "👤 Пользователи":
        if user_id != ADMIN_ID:
            return

        users = get_users()

        text = f"👤 Пользователи: {len(users)}\n\n"

        for i, user in enumerate(users, 1):
            uid, username, first_name, balance = user

            name = first_name or "Без имени"

            if username:
                name += f" (@{username})"

            text += (
                f"{i}. {name}\n"
                f"🆔 {uid}\n"
                f"💰 ${balance:.2f}\n\n"
            )

        await message.answer(text)
        return


    if message.text == "💰 Балансы":
        if user_id != ADMIN_ID:
            return

        users = get_users()

        text = "💰 УПРАВЛЕНИЕ БАЛАНСАМИ\n\n"

        for i, user in enumerate(users, 1):
            uid, username, first_name, balance = user

            name = first_name or "Без имени"

            if username:
                name += f" (@{username})"

            text += (
                f"{i}. {name}\n"
                f"🆔 {uid}\n"
                f"💵 ${balance:.2f}\n\n"
            )

        text += "Для изменения баланса пока используйте ID пользователя."

        await message.answer(text)
        return


    if message.text == "📰 Новости":
        if user_id == ADMIN_ID:
            await message.answer(
                "📰 Управление новостями\n\n"
                "Публикация будет подключена следующим этапом."
            )
        else:
            await message.answer(
                "📰 Новости BLACK RESERVE скоро появятся."
            )
        return


    if message.text == "⚙️ Настройки":
        if user_id != ADMIN_ID:
            return

        await message.answer(
            "⚙️ Настройки\n\n"
            "BLACK RESERVE работает."
        )
        return


    if message.text == "🔙 Главное меню":
        await message.answer(
            "🖤 Главное меню",
            reply_markup=main_menu
        )
        return


    if message.text == "💰 Баланс":
        balance = get_balance(user_id)

        await message.answer(
            f"💰 Ваш баланс: ${balance:.2f}"
        )
        return


    if message.text == "💳 Пополнить":
        await message.answer(
            "💳 Пополнение скоро будет доступно."
        )
        return


    if message.text == "⭐ Отзывы":
        await message.answer(
            "⭐ Отзывы BLACK RESERVE скоро появятся."
        )
        return


    if message.text == "📞 Поддержка":
        await message.answer(
            "📞 Под
