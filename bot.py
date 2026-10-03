import os
import asyncio
import sqlite3
import json
import urllib.request
import urllib.parse
from decimal import Decimal, ROUND_DOWN
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8336765971
DB_NAME = "black_reserve.db"
LTC_ADDRESS = "LYqbDYDAYcB1Pc5F7C59toNQcMJaMWmj2c"
CHECK_INTERVAL = 60

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class DepositState(StatesGroup):
    waiting_usd = State()


def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            usd_amount REAL NOT NULL,
            ltc_amount TEXT NOT NULL,
            txid TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            detected_at TEXT,
            confirmed_at TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_transactions (
            txid TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = db()
    conn.execute(
        """
        INSERT INTO users (user_id, username, first_name, balance)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
        """,
        (user_id, username, first_name),
    )
    conn.commit()
    conn.close()


def get_users():
    conn = db()

    users = conn.execute(
        """
        SELECT user_id, username, first_name, balance
        FROM users
        ORDER BY rowid DESC
        """
    ).fetchall()

    conn.close()
    return users


def get_balance(user_id):
    conn = db()

    result = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    if result is None:
        return 0.0

    return float(result[0])


def change_balance(user_id, amount):
    conn = db()

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def create_deposit(user_id, usd_amount, ltc_amount):
    conn = db()

    now = datetime.utcnow().isoformat()

    cursor = conn.execute(
        """
        INSERT INTO deposits
        (user_id, usd_amount, ltc_amount, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (user_id, usd_amount, ltc_amount, now),
    )

    deposit_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return deposit_id


def get_pending_deposit_by_ltc(ltc_amount):
    conn = db()

    result = conn.execute(
        """
        SELECT id, user_id, usd_amount, ltc_amount
        FROM deposits
        WHERE status = 'pending' AND ltc_amount = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (ltc_amount,),
    ).fetchone()

    conn.close()

    return result


def mark_deposit_detected(deposit_id, txid):
    conn = db()

    now = datetime.utcnow().isoformat()

    conn.execute(
        """
        UPDATE deposits
        SET status = 'detected',
            txid = ?,
            detected_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (txid, now, deposit_id),
    )

    conn.commit()
    conn.close()


def get_deposit(deposit_id):
    conn = db()

    result = conn.execute(
        """
        SELECT id, user_id, usd_amount, ltc_amount, txid, status
        FROM deposits
        WHERE id = ?
        """,
        (deposit_id,),
    ).fetchone()

    conn.close()

    return result


def confirm_deposit(deposit_id):
    conn = db()

    row = conn.execute(
        """
        SELECT user_id, usd_amount, status
        FROM deposits
        WHERE id = ?
        """,
        (deposit_id,),
    ).fetchone()

    if not row:
        conn.close()
        return None

    user_id, usd_amount, status = row

    if status != "detected":
        conn.close()
        return None

    now = datetime.utcnow().isoformat()

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (usd_amount, user_id),
    )

    conn.execute(
        """
        UPDATE deposits
        SET status = 'confirmed',
            confirmed_at = ?
        WHERE id = ? AND status = 'detected'
        """,
        (now, deposit_id),
    )

    conn.commit()
    conn.close()

    return user_id, float(usd_amount)


def reject_deposit(deposit_id):
    conn = db()

    row = conn.execute(
        """
        SELECT user_id, usd_amount, status
        FROM deposits
        WHERE id = ?
        """,
        (deposit_id,),
    ).fetchone()

    if not row:
        conn.close()
        return None

    user_id, usd_amount, status = row

    if status != "detected":
        conn.close()
        return None

    conn.execute(
        """
        UPDATE deposits
        SET status = 'rejected'
        WHERE id = ? AND status = 'detected'
        """,
        (deposit_id,),
    )

    conn.commit()
    conn.close()

    return user_id, float(usd_amount)


def transaction_already_processed(txid):
    conn = db()

    result = conn.execute(
        "SELECT 1 FROM processed_transactions WHERE txid = ?",
        (txid,),
    ).fetchone()

    conn.close()

    return result is not None


def save_processed_transaction(txid):
    conn = db()

    conn.execute(
        """
        INSERT OR IGNORE INTO processed_transactions
        (txid, processed_at)
        VALUES (?, ?)
        """,
        (txid, datetime.utcnow().isoformat()),
    )

    conn.commit()
    conn.close()


def http_get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BLACK-RESERVE-BOT/1.0"
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def get_ltc_usd_rate():
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=litecoin&vs_currencies=usd"
    )

    data = http_get_json(url)

    return Decimal(
        str(data["litecoin"]["usd"])
    )


def get_ltc_transactions():
    address = urllib.parse.quote(
        LTC_ADDRESS,
        safe=""
    )

    url = (
        f"https://api.blockcypher.com/v1/ltc/main/addrs/"
        f"{address}/full?limit=50"
    )

    return http_get_json(url)


def usd_to_unique_ltc(usd_amount):
    rate = get_ltc_usd_rate()

    if rate <= 0:
        raise ValueError("Invalid LTC/USD rate")

    base = (
        Decimal(str(usd_amount)) / rate
    ).quantize(
        Decimal("0.00000001"),
        rounding=ROUND_DOWN,
    )

    conn = db()

    existing = {
        row[0]
        for row in conn.execute(
            """
            SELECT ltc_amount
            FROM deposits
            WHERE status IN ('pending', 'detected')
            """
        ).fetchall()
    }

    conn.close()

    for suffix_number in range(1, 100000):
        suffix = (
            Decimal(suffix_number)
            * Decimal("0.00001")
        )

        candidate = (
            base + suffix
        ).quantize(
            Decimal("0.00000001")
        )

        if candidate <= 0:
            continue

        candidate_text = format(
            candidate,
            "f"
        )

        if candidate_text not in existing:
            return candidate, rate

    raise RuntimeError(
        "Could not create a unique LTC deposit amount"
    )


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📍 Бишкек")
        ],
        [
            KeyboardButton(text="💰 Баланс"),
            KeyboardButton(text="💳 Пополнить"),
        ],
        [
            KeyboardButton(text="📰 Новости"),
            KeyboardButton(text="⭐ Отзывы"),
        ],
        [
            KeyboardButton(text="📞 Поддержка")
        ],
    ],
    resize_keyboard=True,
)


bishkek_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Ленинский район"),
            KeyboardButton(text="Октябрьский район"),
        ],
        [
            KeyboardButton(text="Первомайский район"),
            KeyboardButton(text="Свердловский район"),
        ],
        [
            KeyboardButton(text="🔙 Главное меню")
        ],
    ],
    resize_keyboard=True,
)


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
            KeyboardButton(text="🔙 Главное меню")
        ],
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    await message.answer(
        "🖤 BLACK RESERVE\n\n"
        "Добро пожаловать!",
        reply_markup=main_menu,
    )


@dp.message(Command("admin"))
async def admin_command(
    message: Message,
    state: FSMContext
):
    await state.clear()

    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "⛔ Доступ запрещён."
        )
        return

    await message.answer(
        "⚙️ BLACK RESERVE — ADMIN\n\n"
        "Панель управления:",
        reply_markup=admin_menu,
    )


@dp.message(F.text == "📍 Бишкек")
async def bishkek(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "📍 БИШКЕК\n\n"
        "Выберите район:",
        reply_markup=bishkek_menu,
    )


@dp.message(
    F.text.in_(
        {
            "Ленинский район",
            "Октябрьский район",
            "Первомайский район",
            "Свердловский район",
        }
    )
)
async def district(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        f"📍 БИШКЕК\n"
        f"Район: {message.text}\n\n"
        "Выберите действие:",
        reply_markup=district_menu,
    )


@dp.message(F.text == "🛍️ Позиции")
async def positions(message: Message):
    await message.answer(
        "🛍️ ПОЗИЦИИ\n\n"
        "Позиции этого района скоро будут добавлены."
    )


@dp.message(F.text == "🔙 Районы Бишкек")
async def back_districts(message: Message):
    await message.answer(
        "📍 БИШКЕК\n\n"
        "Выберите район:",
        reply_markup=bishkek_menu,
    )


@dp.message(F.text == "💰 Баланс")
async def balance(message: Message):
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    value = get_balance(
        message.from_user.id
    )

    await message.answer(
        "💰 Ваш баланс: $"
        + format(value, ".2f")
    )


@dp.message(F.text == "💳 Пополнить")
async def deposit_start(
    message: Message,
    state: FSMContext
):
    await state.set_state(
        DepositState.waiting_usd
    )

    await message.answer(
        "💳 ПОПОЛНЕНИЕ\n\n"
        "Введите сумму пополнения в USD.\n"
        "Например: 25"
    )


@dp.message(DepositState.waiting_usd)
async def deposit_amount(
    message: Message,
    state: FSMContext
):
    raw = (
        message.text or ""
    ).replace(",", ".").strip()

    try:
        usd_amount = Decimal(raw)
    except Exception:
        await message.answer(
            "❌ Введите сумму числом. "
            "Например: 25"
        )
        return

    if usd_amount <= 0:
        await message.answer(
            "❌ Сумма должна быть больше 0."
        )
        return

    if usd_amount > Decimal("100000"):
        await message.answer(
            "❌ Максимальная сумма одного "
            "пополнения — $100000."
        )
        return

    try:
        ltc_amount, rate = await asyncio.to_thread(
            usd_to_unique_ltc,
            usd_amount,
        )

        deposit_id = create_deposit(
            message.from_user.id,
            float(usd_amount),
            format(ltc_amount, "f"),
        )

    except Exception as exc:
        print(
            "DEPOSIT CREATE ERROR:",
            repr(exc)
        )

        await state.clear()

        await message.answer(
            "⚠️ Не удалось получить текущий "
            "курс LTC.\n"
            "Попробуйте ещё раз чуть позже.",
            reply_markup=main_menu,
        )
        return

    await state.clear()

    await message.answer(
        "💳 ЗАЯВКА НА ПОПОЛНЕНИЕ\n\n"
        f"💵 Сумма: ${usd_amount:.2f}\n"
        f"🪙 Отправьте: {ltc_amount:.8f} LTC\n\n"
        f"📥 LTC адрес:\n{LTC_ADDRESS}\n\n"
        "После поступления платежа бот "
        "автоматически обнаружит его и "
        "отправит уведомление администратору.\n"
        "После ручной проверки администратор "
        "зачислит средства.\n\n"
        f"🆔 Заявка №{deposit_id}\n"
        f"Курс на момент создания: "
        f"1 LTC ≈ ${rate:.2f}\n\n"
        "⚠️ Отправляйте именно указанную "
        "сумму LTC на указанный адрес.",
        reply_markup=main_menu,
    )


@dp.message(F.text == "📰 Новости")
async def news(message: Message):
    await message.answer(
        "📰 НОВОСТИ BLACK RESERVE\n\n"
        "Новости скоро появятся."
    )


@dp.message(F.text == "⭐ Отзывы")
async def reviews(message: Message):
    await message.answer(
        "⭐ ОТЗЫВЫ BLACK RESERVE\n\n"
        "Отзывы скоро появятся."
    )


@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    await message.answer(
        "📞 ПОДДЕРЖКА BLACK RESERVE\n\n"
        "Раздел поддержки скоро будет настроен."
    )


@dp.message(F.text == "👤 Пользователи")
async def admin_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_users()

    output = (
        f"👤 ПОЛЬЗОВАТЕЛИ\n\n"
        f"Всего: {len(users)}\n\n"
    )

    if not users:
        output += "Пользователей пока нет."

    else:
        for number, user in enumerate(
            users,
            1
        ):
            (
                user_id,
                username,
                first_name,
                balance_value,
            ) = user

            name = (
                first_name
                or "Без имени"
            )

            if username:
                name += (
                    f" (@{username})"
                )

            output += (
                f"{number}. {name}\n"
                f"🆔 {user_id}\n"
                f"💰 ${float(balance_value):.2f}\n\n"
            )

    await message.answer(output)


@dp.message(F.text == "💰 Балансы")
async def admin_balances(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_users()

    output = "💰 БАЛАНСЫ\n\n"

    if not users:
        output += "Пользователей пока нет."

    else:
        for user in users:
            (
                user_id,
                username,
                first_name,
                balance_value,
            ) = user

            name = (
                first_name
                or "Без имени"
            )

            if username:
                name += (
                    f" (@{username})"
                )

            output += (
                f"👤 {name}\n"
                f"🆔 {user_id}\n"
                f"💵 ${float(balance_value):.2f}\n\n"
            )

    await message.answer(output)


@dp.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "⚙️ НАСТРОЙКИ\n\n"
        "🪙 LTC адрес:\n"
        f"{LTC_ADDRESS}\n\n"
        f"⏱ Проверка платежей: "
        f"каждые {CHECK_INTERVAL} сек."
    )


@dp.callback_query(
    F.data.startswith("deposit_confirm:")
)
async def deposit_confirm_callback(
    callback: CallbackQuery
):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )
        return

    try:
        deposit_id = int(
            callback.data.split(
                ":",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):
        await callback.answer(
            "Ошибка заявки.",
            show_alert=True,
        )
        return

    result = confirm_deposit(
        deposit_id
    )

    if result is None:
        await callback.answer(
            "Заявка уже обработана "
            "или не найдена.",
            show_alert=True,
        )
        return

    user_id, usd_amount = result

    await callback.answer(
        "✅ Баланс зачислен."
    )

    try:
        await bot.send_message(
            user_id,
            "✅ ПОПОЛНЕНИЕ ПОДТВЕРЖДЕНО\n\n"
            f"На ваш баланс зачислено: "
            f"${usd_amount:.2f}\n"
            f"💰 Текущий баланс: "
            f"${get_balance(user_id):.2f}",
            reply_markup=main_menu,
        )

    except Exception as exc:
        print(
            "CLIENT NOTIFICATION ERROR:",
            repr(exc)
        )

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )


@dp.callback_query(
    F.data.startswith("deposit_reject:")
)
async def deposit_reject_callback(
    callback: CallbackQuery
):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )
        return

    try:
        deposit_id = int(
            callback.data.split(
                ":",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):
        await callback.answer(
            "Ошибка заявки.",
            show_alert=True,
        )
        return

    result = reject_deposit(
        deposit_id
    )

    if result is None:
        await callback.answer(
            "Заявка уже обработана "
            "или не найдена.",
            show_alert=True,
        )
        return

    user_id, usd_amount = result

    await callback.answer(
        "❌ Заявка отклонена."
    )

    try:
        await bot.send_message(
            user_id,
            "❌ ПОПОЛНЕНИЕ ОТКЛОНЕНО\n\n"
            f"Заявка на ${usd_amount:.2f} "
            "отклонена администратором.",
            reply_markup=main_menu,
        )

    except Exception as exc:
        print(
            "CLIENT NOTIFICATION ERROR:",
            repr(exc)
        )

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )


async def monitor_ltc():
    await asyncio.sleep(10)

    while True:
        try:
            data = await asyncio.to_thread(
                get_ltc_transactions
            )

            txs = data.get(
                "txs",
                []
            )

            for tx in txs:
                txid = tx.get("hash")

                if not txid:
                    continue

                if transaction_already_processed(
                    txid
                ):
                    continue

                found_match = False

                for output in tx.get(
                    "outputs",
                    []
                ):
                    addresses = output.get(
                        "addresses",
                        []
                    )

                    if LTC_ADDRESS not in addresses:
                        continue

                    value_litoshis = int(
                        output.get(
                            "value",
                            0
                        )
                    )

                    received_ltc = (
                        Decimal(value_litoshis)
                        / Decimal("100000000")
                    )

                    received_text = format(
                        received_ltc.quantize(
                            Decimal("0.00000001")
                        ),
                        "f",
                    )

                    deposit = (
                        get_pending_deposit_by_ltc(
                            received_text
                        )
                    )

                    if deposit:
                        (
                            deposit_id,
                            user_id,
                            usd_amount,
                            ltc_amount,
                        ) = deposit

                        mark_deposit_detected(
                            deposit_id,
                            txid
                        )

                        save_processed_transaction(
                            txid
                        )

                        keyboard = (
                            InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text="✅ Подтвердить",
                                            callback_data=(
                                                f"deposit_confirm:"
                                                f"{deposit_id}"
                                            ),
                                        ),
                                        InlineKeyboardButton(
                                            text="❌ Отклонить",
                                            callback_data=(
                                                f"deposit_reject:"
                                                f"{deposit_id}"
                                            ),
                                        ),
                                    ]
                                ]
                            )
                        )

                        await bot.send_message(
                            ADMIN_ID,
                            "🔔 НОВОЕ LTC ПОПОЛНЕНИЕ\n\n"
                            f"🆔 Заявка: #{deposit_id}\n"
                            f"👤 User ID: {user_id}\n"
                            f"💵 Сумма: "
                            f"${float(usd_amount):.2f}\n"
                            f"🪙 Получено: "
                            f"{ltc_amount} LTC\n"
                            f"🔗 TXID:\n{txid}\n\n"
                            "Проверьте транзакцию вручную "
                            "и выберите действие.",
                            reply_markup=keyboard,
                        )

                        found_match = True
                        break

                if not found_match:
                    continue

        except Exception as exc:
            print(
                "LTC MONITOR ERROR:",
                repr(exc)
            )

        await asyncio.sleep(
            CHECK_INTERVAL
        )


async def main():
    init_db()

    monitor_task = asyncio.create_task(
        monitor_ltc()
    )

    print(
        "BLACK RESERVE BOT STARTED"
    )

    try:
        await dp.start_polling(bot)

    finally:
        monitor_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
