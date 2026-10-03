import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Бот запущен и работает."
    )


@dp.message()
async def messages(message: Message):
    await message.answer("🖤 BLACK RESERVE на связи.")


async def main():
    print("BLACK RESERVE BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
