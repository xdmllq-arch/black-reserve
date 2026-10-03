import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from db import init_db, add_user, get_balance, get_users_count


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

    add_user(
        message.from_user.id,
        message.from_user.username
    )

    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать.\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu,
    )


@dp.message()
async def messages(message: Message):

    user_id = message.from_user.id

    add_user(
        user_id,
        message.from_user.username
    )

    # АДМИНКА
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


    # ПОЛЬЗОВАТЕЛИ
    if message.text == "👤 Пользователи":

        if user_id != ADMIN_ID:
            return

        count = get_users_count()

        await message.answer(
            f"👤 Пользователи\n\n"
            f"Всего пользователей: {count}"
        )
        return


    # БАЛАНСЫ
    if message.text == "💰 Балансы":

        if user_id != ADMIN_ID:
            return

        await message.answer(
            "💰 Управление балансами\n\n"
            "Функция изменения баланса будет добавлена следующим этапом."
        )
        return


    # НОВОСТИ
    if message.text == "📰 Новости":

        if user_id == ADMIN_ID:

            await message.answer(
                "📰 Управление новостями\n\n"
                "Добавление новостей будет добавлено следующим этапом."
            )

        else:

            await message.answer(
                "📰 Новости BLACK RESERVE скоро появятся."
            )

        return


    # НАСТРОЙКИ
    if message.text == "⚙️ Настройки":

        if user_id != ADMIN_ID:
            return

        await message.answer(
            "⚙️ Настройки\n\n"
            "BLACK RESERVE работает."
        )
        return


    # ГЛАВНОЕ МЕНЮ
    if message.text == "🔙 Главное меню":

        await message.answer(
            "🖤 Главное меню",
            reply_markup=main_menu,
        )
        return


    # БАЛАНС ПОЛЬЗОВАТЕЛЯ
    if message.text == "💰 Баланс":

        balance = get_balance(user_id)

        await message.answer(
            f"💰 Ваш баланс: ${balance:.2f}"
        )
        return


    # ПОПОЛНЕНИЕ
    if message.text == "💳 Пополнить":

        await message.answer(
            "💳 Пополнение баланса будет подключено следующим этапом."
        )
        return


    # ОТЗЫВЫ
    if message.text == "⭐ Отзывы":

        await message.answer(
            "⭐ Отзывы BLACK RESERVE скоро появятся."
        )
        return


    # ПОДДЕРЖКА
    if message.text == "📞 Поддержка":

        await message.answer(
            "📞 Поддержка BLACK RESERVE."
        )
        return


    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Выберите раздел в меню.",
        reply_markup=main_menu,
    )


async def main():

    init_db()

    print("BLACK RESERVE BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
