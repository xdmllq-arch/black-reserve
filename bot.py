import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
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

        await message.answer(
            "👤 Пользователи\n\n"
            "Система пользователей будет подключена следующим этапом."
        )
        return


    if message.text == "💰 Балансы":
        if user_id != ADMIN_ID:
            return

        await message.answer(
            "💰 Балансы\n\n"
            "Управление балансами будет подключено следующим этапом."
        )
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
        await message.answer("💰 Ваш баланс: $0.00")
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
            "📞 Поддержка BLACK RESERVE."
        )
        return


    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Выберите раздел.",
        reply_markup=main_menu
    )


async def main():
    print("BLACK RESERVE BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
