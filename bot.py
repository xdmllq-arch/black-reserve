import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8336765971

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать.\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu,
    )


@dp.message()
async def messages(message: Message):

    # АДМИНКА
    if message.text == "/admin":
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔ Доступ запрещён.")
            return

        await message.answer(
            "⚙️ АДМИН-ПАНЕЛЬ\n\n"
            "Выберите раздел:",
            reply_markup=admin_menu,
        )
        return

    if message.text == "👤 Пользователи":
        if message.from_user.id != ADMIN_ID:
            return

        await message.answer(
            "👤 Пользователи\n\n"
            "Пользователей пока: 1"
        )
        return

    if message.text == "💰 Балансы":
        if message.from_user.id != ADMIN_ID:
            return

        await message.answer(
            "💰 Управление балансами\n\n"
            "Функция управления балансами готовится."
        )
        return

    if message.text == "📰 Новости":
        if message.from_user.id == ADMIN_ID:
            await message.answer(
                "📰 Управление новостями\n\n"
                "Добавление и редактирование новостей скоро будет доступно."
            )
        else:
            await message.answer(
                "📰 Новости BLACK RESERVE скоро появятся."
            )
        return

    if message.text == "⚙️ Настройки":
        if message.from_user.id != ADMIN_ID:
            return

        await message.answer(
            "⚙️ Настройки\n\n"
            "BLACK RESERVE работает."
        )
        return

    if message.text == "🔙 Главное меню":
        await message.answer(
            "🖤 Главное меню",
            reply_markup=main_menu,
        )
        return

    # ОСНОВНОЕ МЕНЮ
    if message.text == "💰 Баланс":
        await message.answer("💰 Ваш баланс: $0.00")

    elif message.text == "💳 Пополнить":
        await message.answer(
            "💳 Раздел пополнения скоро будет доступен."
        )

    elif message.text == "⭐ Отзывы":
        await message.answer(
            "⭐ Отзывы BLACK RESERVE скоро появятся."
        )

    elif message.text == "📞 Поддержка":
        await message.answer(
            "📞 Поддержка BLACK RESERVE."
        )

    else:
        await message.answer(
            "🖤 BLACK RESERVE\n\n"
            "Выберите раздел в меню.",
            reply_markup=main_menu,
        )


async def main():
    print("BLACK RESERVE BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
