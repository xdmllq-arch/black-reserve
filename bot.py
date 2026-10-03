import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

menu = ReplyKeyboardMarkup(
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
        "Добро пожаловать!",
        reply_markup=menu
    )


@dp.message()
async def message_handler(message: Message):
    if message.text == "💰 Баланс":
        await message.answer("💰 Ваш баланс: $0.00")

    elif message.text == "💳 Пополнить":
        await message.answer("💳 Пополнение скоро будет доступно.")

    elif message.text == "📰 Новости":
        await message.answer("📰 Новости скоро появятся.")

    elif message.text == "⭐ Отзывы":
        await message.answer("⭐ Отзывы скоро появятся.")

    elif message.text == "📞 Поддержка":
        await message.answer("📞 Поддержка BLACK RESERVE.")

    else:
        await message.answer(
            "🖤 BLACK RESERVE\n\n"
            "Выберите раздел.",
            reply_markup=menu
        )


async def main():
    print("BLACK RESERVE BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
