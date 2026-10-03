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
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
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

DISTRICTS = {
    "Ленинский район",
    "Октябрьский район",
    "Первомайский район",
    "Свердловский район",
}


class DepositState(StatesGroup):
    waiting_usd = State()


class ProductAddState(StatesGroup):
    name = State()
    price = State()
    description = State()
    photo = State()
    district = State()


class ProductEditState(StatesGroup):
    product_id = State()
    value = State()


def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0
        )
    """)

    conn.execute("""
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
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_transactions (
            txid TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            photo_file_id TEXT,
            district TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = db()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, balance)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def get_users():
    conn = db()
    users = conn.execute("""
        SELECT user_id, username, first_name, balance
        FROM users ORDER BY rowid DESC
    """).fetchall()
    conn.close()
    return users


def get_balance(user_id):
    conn = db()
    result = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return float(result[0]) if result else 0.0


def create_deposit(user_id, usd_amount, ltc_amount):
    conn = db()
    cursor = conn.execute("""
        INSERT INTO deposits
        (user_id, usd_amount, ltc_amount, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    """, (user_id, usd_amount, ltc_amount, datetime.utcnow().isoformat()))
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deposit_id


def get_pending_deposit_by_ltc(ltc_amount):
    conn = db()
    result = conn.execute("""
        SELECT id, user_id, usd_amount, ltc_amount
        FROM deposits
        WHERE status = 'pending' AND ltc_amount = ?
        ORDER BY id ASC LIMIT 1
    """, (ltc_amount,)).fetchone()
    conn.close()
    return result


def mark_deposit_detected(deposit_id, txid):
    conn = db()
    conn.execute("""
        UPDATE deposits
        SET status = 'detected', txid = ?, detected_at = ?
        WHERE id = ? AND status = 'pending'
    """, (txid, datetime.utcnow().isoformat(), deposit_id))
    conn.commit()
    conn.close()


def confirm_deposit(deposit_id):
    conn = db()
    row = conn.execute("""
        SELECT user_id, usd_amount, status
        FROM deposits WHERE id = ?
    """, (deposit_id,)).fetchone()

    if not row or row[2] != "detected":
        conn.close()
        return None

    user_id, usd_amount, _ = row
    now = datetime.utcnow().isoformat()

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (usd_amount, user_id)
    )
    conn.execute("""
        UPDATE deposits
        SET status = 'confirmed', confirmed_at = ?
        WHERE id = ? AND status = 'detected'
    """, (now, deposit_id))

    conn.commit()
    conn.close()
    return user_id, float(usd_amount)


def reject_deposit(deposit_id):
    conn = db()
    row = conn.execute("""
        SELECT user_id, usd_amount, status
        FROM deposits WHERE id = ?
    """, (deposit_id,)).fetchone()

    if not row or row[2] != "detected":
        conn.close()
        return None

    user_id, usd_amount, _ = row
    conn.execute("""
        UPDATE deposits SET status = 'rejected'
        WHERE id = ? AND status = 'detected'
    """, (deposit_id,))
    conn.commit()
    conn.close()
    return user_id, float(usd_amount)


def transaction_already_processed(txid):
    conn = db()
    result = conn.execute(
        "SELECT 1 FROM processed_transactions WHERE txid = ?", (txid,)
    ).fetchone()
    conn.close()
    return result is not None


def save_processed_transaction(txid):
    conn = db()
    conn.execute("""
        INSERT OR IGNORE INTO processed_transactions
        (txid, processed_at) VALUES (?, ?)
    """, (txid, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ---------- CATALOG ----------

def add_product(name, price, description, photo_file_id, district):
    now = datetime.utcnow().isoformat()
    conn = db()
    cur = conn.execute("""
        INSERT INTO products
        (name, price, description, photo_file_id, district, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, price, description, photo_file_id, district, now, now))
    product_id = cur.lastrowid
    conn.commit()
    conn.close()
    return product_id


def get_products(district=None):
    conn = db()
    if district:
        rows = conn.execute("""
            SELECT id, name, price, description, photo_file_id, district
            FROM products WHERE district = ? ORDER BY id DESC
        """, (district,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, name, price, description, photo_file_id, district
            FROM products ORDER BY id DESC
        """).fetchall()
    conn.close()
    return rows


def get_product(product_id):
    conn = db()
    row = conn.execute("""
        SELECT id, name, price, description, photo_file_id, district
        FROM products WHERE id = ?
    """, (product_id,)).fetchone()
    conn.close()
    return row


def update_product_field(product_id, field, value):
    allowed = {
        "name", "price", "description", "photo_file_id", "district"
    }
    if field not in allowed:
        return False

    conn = db()
    conn.execute(
        f"UPDATE products SET {field} = ?, updated_at = ? WHERE id = ?",
        (value, datetime.utcnow().isoformat(), product_id)
    )
    changed = conn.total_changes > 0
    conn.commit()
    conn.close()
    return changed


def delete_product(product_id):
    conn = db()
    cur = conn.execute(
        "DELETE FROM products WHERE id = ?", (product_id,)
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def product_text(row):
    product_id, name, price, description, photo, district = row
    text = (
        f"🛍️ {name}\n"
        f"💵 Цена: ${float(price):.2f}\n"
    )
    if description:
        text += f"\n📝 {description}\n"
    return text


def catalog_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить позицию")],
            [KeyboardButton(text="📋 Список позиций")],
            [KeyboardButton(text="✏️ Изменить позицию")],
            [KeyboardButton(text="💰 Изменить цену")],
            [KeyboardButton(text="📝 Изменить описание")],
            [KeyboardButton(text="🖼 Изменить фото")],
            [KeyboardButton(text="📍 Изменить район")],
            [KeyboardButton(text="🗑 Удалить позицию")],
            [KeyboardButton(text="🔙 Админ-панель")],
        ],
        resize_keyboard=True
    )


# ---------- LTC ----------

def http_get_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "BLACK-RESERVE-BOT/1.0"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_ltc_usd_rate():
    data = http_get_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=litecoin&vs_currencies=usd"
    )
    return Decimal(str(data["litecoin"]["usd"]))


def get_ltc_transactions():
    address = urllib.parse.quote(LTC_ADDRESS, safe="")
    return http_get_json(
        f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full?limit=50"
    )


def usd_to_unique_ltc(usd_amount):
    rate = get_ltc_usd_rate()
    if rate <= 0:
        raise ValueError("Invalid LTC/USD rate")

    base = (Decimal(str(usd_amount)) / rate).quantize(
        Decimal("0.00000001"), rounding=ROUND_DOWN
    )

    conn = db()
    existing = {
        row[0] for row in conn.execute("""
            SELECT ltc_amount FROM deposits
            WHERE status IN ('pending', 'detected')
        """).fetchall()
    }
    conn.close()

    for suffix_number in range(1, 100000):
        candidate = (
            base + Decimal(suffix_number) * Decimal("0.00001")
        ).quantize(Decimal("0.00000001"))

        if candidate <= 0:
            continue

        text_value = format(candidate, "f")
        if text_value not in existing:
            return candidate, rate

    raise RuntimeError("Could not create a unique LTC deposit amount")


# ---------- KEYBOARDS ----------

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Бишкек")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💳 Пополнить")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="📞 Поддержка")],
    ],
    resize_keyboard=True
)

bishkek_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Ленинский район"), KeyboardButton(text="Октябрьский район")],
        [KeyboardButton(text="Первомайский район"), KeyboardButton(text="Свердловский район")],
        [KeyboardButton(text="🔙 Главное меню")],
    ],
    resize_keyboard=True
)

district_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍️ Позиции")],
        [KeyboardButton(text="🔙 Районы Бишкек")],
        [KeyboardButton(text="🏠 Главное меню")],
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Пользователи"), KeyboardButton(text="💰 Балансы")],
        [KeyboardButton(text="🛍 Каталог")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🔙 Главное меню")],
    ],
    resize_keyboard=True
)


# ---------- CLIENT ----------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    await message.answer(
        "🖤 BLACK RESERVE\n\nДобро пожаловать!",
        reply_markup=main_menu
    )


@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "⚙️ BLACK RESERVE — ADMIN\n\nПанель управления:",
        reply_markup=admin_menu
    )


@dp.message(F.text == "📍 Бишкек")
async def bishkek(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📍 БИШКЕК\n\nВыберите район:",
        reply_markup=bishkek_menu
    )


@dp.message(F.text.in_(DISTRICTS))
async def district(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(selected_district=message.text)
    await message.answer(
        f"📍 БИШКЕК\nРайон: {message.text}\n\nВыберите действие:",
        reply_markup=district_menu
    )


@dp.message(F.text == "🛍️ Позиции")
async def positions(message: Message, state: FSMContext):
    data = await state.get_data()
    district_name = data.get("selected_district")

    if not district_name:
        await message.answer(
            "Сначала выберите район.",
            reply_markup=bishkek_menu
        )
        return

    rows = get_products(district_name)
    if not rows:
        await message.answer(
            f"🛍️ ПОЗИЦИИ\n\n"
            f"Район: {district_name}\n\n"
            "Позиции пока отсутствуют."
        )
        return

    await message.answer(
        f"🛍️ ПОЗИЦИИ\n\nРайон: {district_name}\n\n"
        f"Найдено позиций: {len(rows)}"
    )

    for row in rows:
        text = product_text(row)
        if row[4]:
            try:
                await message.answer_photo(row[4], caption=text)
            except Exception:
                await message.answer(text)
        else:
            await message.answer(text)


@dp.message(F.text == "🔙 Районы Бишкек")
async def back_districts(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📍 БИШКЕК\n\nВыберите район:",
        reply_markup=bishkek_menu
    )


@dp.message(F.text == "💰 Баланс")
async def balance(message: Message):
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    await message.answer(
        "💰 Ваш баланс: $" + format(
            get_balance(message.from_user.id), ".2f"
        )
    )


@dp.message(F.text == "💳 Пополнить")
async def deposit_start(message: Message, state: FSMContext):
    await state.set_state(DepositState.waiting_usd)
    await message.answer(
        "💳 ПОПОЛНЕНИЕ\n\n"
        "Введите сумму пополнения в USD.\n"
        "Например: 25"
    )


@dp.message(DepositState.waiting_usd)
async def deposit_amount(message: Message, state: FSMContext):
    raw = (message.text or "").replace(",", ".").strip()

    try:
        usd_amount = Decimal(raw)
    except Exception:
        await message.answer("❌ Введите сумму числом. Например: 25")
        return

    if usd_amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0.")
        return

    if usd_amount > Decimal("100000"):
        await message.answer("❌ Максимальная сумма одного пополнения — $100000.")
        return

    try:
        ltc_amount, rate = await asyncio.to_thread(
            usd_to_unique_ltc, usd_amount
        )
        deposit_id = create_deposit(
            message.from_user.id,
            float(usd_amount),
            format(ltc_amount, "f")
        )
    except Exception as exc:
        print("DEPOSIT CREATE ERROR:", repr(exc))
        await state.clear()
        await message.answer(
            "⚠️ Не удалось получить текущий курс LTC.\n"
            "Попробуйте ещё раз чуть позже.",
            reply_markup=main_menu
        )
        return

    await state.clear()
    await message.answer(
        "💳 ЗАЯВКА НА ПОПОЛНЕНИЕ\n\n"
        f"💵 Сумма: ${usd_amount:.2f}\n"
        f"🪙 Отправьте: {ltc_amount:.8f} LTC\n\n"
        f"📥 LTC адрес:\n{LTC_ADDRESS}\n\n"
        "После поступления платежа бот автоматически обнаружит его "
        "и отправит уведомление администратору.\n"
        "После ручной проверки администратор зачислит средства.\n\n"
        f"🆔 Заявка №{deposit_id}\n"
        f"Курс на момент создания: 1 LTC ≈ ${rate:.2f}\n\n"
        "⚠️ Отправляйте именно указанную сумму LTC на указанный адрес.",
        reply_markup=main_menu
    )


@dp.message(F.text == "📰 Новости")
async def news(message: Message):
    await message.answer(
        "📰 НОВОСТИ BLACK RESERVE\n\nНовости скоро появятся."
    )


@dp.message(F.text == "⭐ Отзывы")
async def reviews(message: Message):
    await message.answer(
        "⭐ ОТЗЫВЫ BLACK RESERVE\n\nОтзывы скоро появятся."
    )


@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    await message.answer(
        "📞 ПОДДЕРЖКА BLACK RESERVE\n\n"
        "Раздел поддержки скоро будет настроен."
    )


# ---------- ADMIN BASIC ----------

@dp.message(F.text == "👤 Пользователи")
async def admin_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_users()
    output = f"👤 ПОЛЬЗОВАТЕЛИ\n\nВсего: {len(users)}\n\n"

    if not users:
        output += "Пользователей пока нет."
    else:
        for number, user in enumerate(users, 1):
            user_id, username, first_name, balance_value = user
            name = first_name or "Без имени"
            if username:
                name += f" (@{username})"
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
            user_id, username, first_name, balance_value = user
            name = first_name or "Без имени"
            if username:
                name += f" (@{username})"
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
        f"🪙 LTC адрес:\n{LTC_ADDRESS}\n\n"
        f"⏱ Проверка платежей: каждые {CHECK_INTERVAL} сек."
    )


@dp.message(F.text == "🔙 Админ-панель")
async def back_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("⚙️ Админ-панель:", reply_markup=admin_menu)


@dp.message(F.text == "🛍 Каталог")
async def admin_catalog(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer(
        "🛍️ УПРАВЛЕНИЕ КАТАЛОГОМ",
        reply_markup=catalog_admin_menu()
    )


@dp.message(F.text == "📋 Список позиций")
async def admin_product_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = get_products()
    if not rows:
        await message.answer("📋 Каталог пуст.")
        return

    for row in rows:
        await message.answer(
            f"ID: {row[0]}\n"
            f"📍 {row[5]}\n\n"
            + product_text(row)
        )


# ---------- ADD PRODUCT ----------

@dp.message(F.text == "➕ Добавить позицию")
async def add_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(ProductAddState.name)
    await message.answer(
        "➕ ДОБАВЛЕНИЕ ПОЗИЦИИ\n\n"
        "Введите название позиции:"
    )


@dp.message(ProductAddState.name)
async def add_product_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название не может быть пустым.")
        return
    await state.update_data(name=name)
    await state.set_state(ProductAddState.price)
    await message.answer("Введите цену в USD, например: 25")


@dp.message(ProductAddState.price)
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = float((message.text or "").replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите цену числом, например: 25")
        return

    if price < 0:
        await message.answer("❌ Цена не может быть отрицательной.")
        return

    await state.update_data(price=price)
    await state.set_state(ProductAddState.description)
    await message.answer(
        "Введите описание позиции.\n"
        "Если описание не нужно — отправьте: -"
    )


@dp.message(ProductAddState.description)
async def add_product_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    if description == "-":
        description = ""
    await state.update_data(description=description)
    await state.set_state(ProductAddState.photo)
    await message.answer(
        "Отправьте фото позиции.\n"
        "Если фото не нужно — отправьте текст: -"
    )


@dp.message(ProductAddState.photo)
async def add_product_photo(message: Message, state: FSMContext):
    photo_id = None

    if message.photo:
        photo_id = message.photo[-1].file_id
    elif (message.text or "").strip() != "-":
        await message.answer(
            "❌ Нужна фотография или отправьте: -"
        )
        return

    await state.update_data(photo_file_id=photo_id)
    await state.set_state(ProductAddState.district)
    await message.answer(
        "Выберите район текстом:\n\n"
        "Ленинский район\n"
        "Октябрьский район\n"
        "Первомайский район\n"
        "Свердловский район"
    )


@dp.message(ProductAddState.district)
async def add_product_district(message: Message, state: FSMContext):
    district = (message.text or "").strip()
    if district not in DISTRICTS:
        await message.answer(
            "❌ Неверный район. Выберите один из четырёх:\n\n"
            + "\n".join(sorted(DISTRICTS))
        )
        return

    data = await state.get_data()
    product_id = add_product(
        data["name"],
        data["price"],
        data["description"],
        data.get("photo_file_id"),
        district
    )

    await state.clear()
    await message.answer(
        f"✅ Позиция добавлена!\n\n"
        f"ID: {product_id}\n"
        f"📍 Район: {district}\n"
        f"🛍️ {data['name']}\n"
        f"💵 ${float(data['price']):.2f}",
        reply_markup=catalog_admin_menu()
    )


# ---------- EDIT PRODUCT ----------

async def ask_edit_id(message: Message, state: FSMContext, action_text: str, next_state):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(next_state)
    await message.answer(
        f"{action_text}\n\n"
        "Введите ID позиции.\n"
        "ID можно посмотреть через «📋 Список позиций»."
    )


@dp.message(F.text == "✏️ Изменить позицию")
async def edit_product_start(message: Message, state: FSMContext):
    await ask_edit_id(message, state, "✏️ ИЗМЕНИТЬ НАЗВАНИЕ", ProductEditState.product_id)
    await state.update_data(edit_field="name")


@dp.message(F.text == "💰 Изменить цену")
async def edit_price_start(message: Message, state: FSMContext):
    await ask_edit_id(message, state, "💰 ИЗМЕНИТЬ ЦЕНУ", ProductEditState.product_id)
    await state.update_data(edit_field="price")


@dp.message(F.text == "📝 Изменить описание")
async def edit_description_start(message: Message, state: FSMContext):
    await ask_edit_id(message, state, "📝 ИЗМЕНИТЬ ОПИСАНИЕ", ProductEditState.product_id)
    await state.update_data(edit_field="description")


@dp.message(F.text == "🖼 Изменить фото")
async def edit_photo_start(message: Message, state: FSMContext):
    await ask_edit_id(message, state, "🖼 ИЗМЕНИТЬ ФОТО", ProductEditState.product_id)
    await state.update_data(edit_field="photo_file_id")


@dp.message(F.text == "📍 Изменить район")
async def edit_district_start(message: Message, state: FSMContext):
    await ask_edit_id(message, state, "📍 ИЗМЕНИТЬ РАЙОН", ProductEditState.product_id)
    await state.update_data(edit_field="district")


@dp.message(ProductEditState.product_id)
async def edit_product_id(message: Message, state: FSMContext):
    try:
        product_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Введите ID числом.")
        return

    row = get_product(product_id)
    if not row:
        await message.answer("❌ Позиция с таким ID не найдена.")
        return

    data = await state.get_data()
    field = data.get("edit_field")
    await state.update_data(product_id=product_id)

    prompts = {
        "name": "Введите новое название:",
        "price": "Введите новую цену в USD:",
        "description": "Введите новое описание. Для пустого описания отправьте: -",
        "photo_file_id": "Отправьте новое фото.",
        "district": (
            "Введите новый район:\n\n"
            "Ленинский район\n"
            "Октябрьский район\n"
            "Первомайский район\n"
            "Свердловский район"
        )
    }

    await state.set_state(ProductEditState.value)
    await message.answer(
        f"Текущая позиция:\n\n{product_text(row)}\n\n"
        + prompts[field]
    )


@dp.message(ProductEditState.value)
async def edit_product_value(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")
    field = data.get("edit_field")

    if not product_id or not field:
        await state.clear()
        await message.answer("❌ Сессия редактирования сброшена.")
        return

    if field == "name":
        value = (message.text or "").strip()
        if not value:
            await message.answer("❌ Название не может быть пустым.")
            return

    elif field == "price":
        try:
            value = float((message.text or "").replace(",", ".").strip())
        except ValueError:
            await message.answer("❌ Введите цену числом.")
            return
        if value < 0:
            await message.answer("❌ Цена не может быть отрицательной.")
            return

    elif field == "description":
        value = (message.text or "").strip()
        if value == "-":
            value = ""

    elif field == "photo_file_id":
        if not message.photo:
            await message.answer("❌ Отправьте именно фотографию.")
            return
        value = message.photo[-1].file_id

    elif field == "district":
        value = (message.text or "").strip()
        if value not in DISTRICTS:
            await message.answer(
                "❌ Неверный район. Выберите один из четырёх."
            )
            return

    else:
        await state.clear()
        return

    update_product_field(product_id, field, value)
    row = get_product(product_id)
    await state.clear()

    await message.answer(
        "✅ Позиция обновлена!\n\n"
        + product_text(row),
        reply_markup=catalog_admin_menu()
    )


# ---------- DELETE PRODUCT ----------

@dp.message(F.text == "🗑 Удалить позицию")
async def delete_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(ProductEditState.product_id)
    await state.update_data(edit_field="delete")
    await message.answer(
        "🗑 УДАЛЕНИЕ ПОЗИЦИИ\n\n"
        "Введите ID позиции, которую нужно удалить."
    )


@dp.message(F.text, ProductEditState.product_id)
async def delete_product_id(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("edit_field") != "delete":
        return

    try:
        product_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Введите ID числом.")
        return

    row = get_product(product_id)
    if not row:
        await message.answer("❌ Позиция с таким ID не найдена.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"product_delete_yes:{product_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"product_delete_no:{product_id}"
        )
    ]])

    await state.clear()
    await message.answer(
        "⚠️ Удалить эту позицию?\n\n" + product_text(row),
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("product_delete_yes:"))
async def delete_product_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    product_id = int(callback.data.split(":", 1)[1])
    if delete_product(product_id):
        await callback.answer("Удалено.")
        await callback.message.edit_text("✅ Позиция удалена.")
    else:
        await callback.answer("Позиция не найдена.", show_alert=True)


@dp.callback_query(F.data.startswith("product_delete_no:"))
async def delete_product_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    await callback.answer("Отмена")
    await callback.message.edit_text("❌ Удаление отменено.")


# ---------- DEPOSIT CALLBACKS ----------

@dp.callback_query(F.data.startswith("deposit_confirm:"))
async def deposit_confirm_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        deposit_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка заявки.", show_alert=True)
        return

    result = confirm_deposit(deposit_id)
    if result is None:
        await callback.answer(
            "Заявка уже обработана или не найдена.",
            show_alert=True
        )
        return

    user_id, usd_amount = result
    await callback.answer("✅ Баланс зачислен.")

    try:
        await bot.send_message(
            user_id,
            "✅ ПОПОЛНЕНИЕ ПОДТВЕРЖДЕНО\n\n"
            f"На ваш баланс зачислено: ${usd_amount:.2f}\n"
            f"💰 Текущий баланс: ${get_balance(user_id):.2f}",
            reply_markup=main_menu
        )
    except Exception as exc:
        print("CLIENT NOTIFICATION ERROR:", repr(exc))

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@dp.callback_query(F.data.startswith("deposit_reject:"))
async def deposit_reject_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        deposit_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка заявки.", show_alert=True)
        return

    result = reject_deposit(deposit_id)
    if result is None:
        await callback.answer(
            "Заявка уже обработана или не найдена.",
            show_alert=True
        )
        return

    user_id, usd_amount = result
    await callback.answer("❌ Заявка отклонена.")

    try:
        await bot.send_message(
            user_id,
            "❌ ПОПОЛНЕНИЕ ОТКЛОНЕНО\n\n"
            f"Заявка на ${usd_amount:.2f} отклонена администратором.",
            reply_markup=main_menu
        )
    except Exception as exc:
        print("CLIENT NOTIFICATION ERROR:", repr(exc))

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


# ---------- LTC MONITOR ----------

async def monitor_ltc():
    await asyncio.sleep(10)

    while True:
        try:
            data = await asyncio.to_thread(get_ltc_transactions)
            txs = data.get("txs", [])

            for tx in txs:
                txid = tx.get("hash")
                if not txid or transaction_already_processed(txid):
                    continue

                for output in tx.get("outputs", []):
                    addresses = output.get("addresses", [])
                    if LTC_ADDRESS not in addresses:
                        continue

                    value_litoshis = int(output.get("value", 0))
                    received_ltc = (
                        Decimal(value_litoshis) / Decimal("100000000")
                    )
                    received_text = format(
                        received_ltc.quantize(Decimal("0.00000001")), "f"
                    )

                    deposit = get_pending_deposit_by_ltc(received_text)
                    if not deposit:
                        continue

                    deposit_id, user_id, usd_amount, ltc_amount = deposit

                    mark_deposit_detected(deposit_id, txid)
                    save_processed_transaction(txid)

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"deposit_confirm:{deposit_id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"deposit_reject:{deposit_id}"
                        )
                    ]])

                    await bot.send_message(
                        ADMIN_ID,
                        "🔔 НОВОЕ LTC ПОПОЛНЕНИЕ\n\n"
                        f"🆔 Заявка: #{deposit_id}\n"
                        f"👤 User ID: {user_id}\n"
                        f"💵 Сумма: ${float(usd_amount):.2f}\n"
                        f"🪙 Получено: {ltc_amount} LTC\n"
                        f"🔗 TXID:\n{txid}\n\n"
                        "Проверьте транзакцию вручную и выберите действие.",
                        reply_markup=keyboard
                    )
                    break

        except Exception as exc:
            print("LTC MONITOR ERROR:", repr(exc))

        await asyncio.sleep(CHECK_INTERVAL)


async def main():
    init_db()

    monitor_task = asyncio.create_task(monitor_ltc())
    print("BLACK RESERVE BOT STARTED")

    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
