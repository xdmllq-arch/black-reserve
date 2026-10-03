import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
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


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать.\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu,
    )


@dp.message()
async def menu(message: Message):
    if message.text == "💰 Баланс":
        await message.answer("💰 Ваш баланс: $0.00")

    elif message.text == "💳 Пополнить":
        await message.answer(
            "💳 Раздел пополнения скоро будет доступен."
        )

    elif message.text == "📰 Новости":
        await message.answer(
            "📰 Новости BLACK RESERVE скоро появятся."
        )

    elif message.text == "⭐ Отзывы":
        await message.answer(
            "⭐ Отзывы BLACK RESERVE скоро появятся."
        )

    elif message.text == "📞 Поддержка":
        await message.answer(
            "📞 Поддержка: напишите администратору."
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
