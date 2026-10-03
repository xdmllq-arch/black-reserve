import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from db import init_db, add_user, get_balance, get_users_count, change_balance

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8336765971

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💳 Пополнить")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="📞 Поддержка")],
    ],
    resize_keyboard=True,
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Пользователи"), KeyboardButton(text="💰 Балансы")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🔙 Главное меню")],
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def start(message: Message):
    add_user(message.from_user.id, message.from_user.username)

    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать.\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu,
    )


@dp.message()
async def messages(message: Message):
    user_id = message.from_user.id

    add_user(user_id, message.from_user.username)

    if message.text == "/admin":
        if user_id != ADMIN_ID:
            await message.answer("⛔ Доступ запрещён.")
            return

        await message.answer(
            "⚙️ АДМИН-ПАНЕЛЬ\n\n"
            "Выберите раздел:",
            reply_markup=admin_menu,
        )
        return

    if message.text == "👤 Пользователи":
        if user_id != ADMIN_ID:
            return

        count = get_users_count()
        await message.answer(f"👤 Пользователи\n\nВсего пользователей: {count}")
        return

    if message.text == "💰 Балансы":
        if user_id != ADMIN_ID:
            return

        await message.answer(
            "💰 Управление балансом\n\n"
            "Эта функция будет настроена следующим шагом."
        )
        return

    if message.text == "💰 Баланс":
        balance = get_balance(user_id)
        await message.answer(f"💰 Ваш баланс: ${balance:.2f}")
        return

    if message.text == "💳 Пополнить":
        await message.answer("💳 Пополнение скоро будет доступно.")
        return

    if message.text == "📰 Новости":
        await message.answer("📰 Новости BLACK RESERVE скоро появятся.")
        return

    if message.text == "⭐ Отзывы":
        await message.answer("⭐ Отзывы BLACK RESERVE скоро появятся.")
        return

    if message.text == "📞 Поддержка":
        await message.answer("📞 Поддержка BLACK RESERVE.")
        return

    if message.text == "⚙️ Настройки":
        if user_id != ADMIN_ID:
            return

        await message.answer("⚙️ Настройки\n\nBLACK RESERVE работает.")
        return

    if message.text == "🔙 Главное меню":
        await message.answer(
            "🖤 Главное меню",
            reply_markup=main_menu,
        )
        return

    await message.answer(
        "🖤 BLACK RESERVE\n\nВыберите раздел.",
        reply_markup=main_menu,
    )


async def main():
    init_db()
    print("BLACK RESERVE BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
