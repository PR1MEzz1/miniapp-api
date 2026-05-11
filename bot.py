import asyncio
import json
import os
import threading
import aiohttp
from datetime import datetime
from urllib.parse import quote
from flask import Flask

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 588097726
MINI_APP_URL = "https://singular-mooncake-c8c1b8.netlify.app"
API_URL = "https://miniapp-api2.onrender.com"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "notifications.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

bot = Bot(token=TOKEN)
dp = Dispatcher()

health_app = Flask(__name__)


@health_app.route("/")
def health():
    return "Bot is running", 200


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    health_app.run(host="0.0.0.0", port=port)


class AddProduct(StatesGroup):
    name = State()
    category = State()
    price = State()
    old_price = State()
    stock = State()
    desc = State()
    image = State()


class EditProduct(StatesGroup):
    product_id = State()
    price = State()
    stock = State()


class DeleteProduct(StatesGroup):
    product_id = State()


class ToggleProduct(StatesGroup):
    product_id = State()


def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def load_json(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        return json.loads(text) if text else default
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)

    for path in [USERS_FILE, ORDERS_FILE, NOTIFICATIONS_FILE]:
        if not os.path.exists(path):
            save_json(path, [])

    if not os.path.exists(SETTINGS_FILE):
        save_json(SETTINGS_FILE, {
            "store_name": "Premium Store",
            "support": "@zzleedzz",
            "currency": "₽"
        })


def get_user(user_id):
    users = load_json(USERS_FILE, [])
    for user in users:
        if user.get("telegram_id") == user_id:
            return user
    return None


def save_user_from_contact(message: Message):
    users = load_json(USERS_FILE, [])
    old = get_user(message.from_user.id)

    user = {
        "telegram_id": message.from_user.id,
        "first_name": message.from_user.first_name or "Клиент",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
        "phone": message.contact.phone_number,
        "role": "admin" if message.from_user.id == ADMIN_ID else "user",
        "bonus": old.get("bonus", 500) if old else 500,
        "vip_status": old.get("vip_status", "basic") if old else "basic",
        "created_at": old.get("created_at") if old else now(),
        "updated_at": now(),
    }

    users = [u for u in users if u.get("telegram_id") != message.from_user.id]
    users.append(user)
    save_json(USERS_FILE, users)
    return user


def mini_app_link(user):
    uid = quote(str(user.get("telegram_id", "")))
    name = quote(user.get("first_name", "Клиент"))
    phone = quote(user.get("phone", ""))
    role = quote(user.get("role", "user"))
    bonus = quote(str(user.get("bonus", 500)))
    vip = quote(user.get("vip_status", "basic"))

    return (
        f"{MINI_APP_URL}"
        f"?uid={uid}"
        f"&name={name}"
        f"&phone={phone}"
        f"&role={role}"
        f"&bonus={bonus}"
        f"&vip={vip}"
    )


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться телефоном", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def main_keyboard(user):
    keyboard = [
        [
            KeyboardButton(
                text="🛍 Открыть Premium Store",
                web_app=WebAppInfo(url=mini_app_link(user))
            )
        ],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📦 Мои заказы")],
        [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="📞 Поддержка")]
    ]

    if user and user.get("role") == "admin":
        keyboard.append([KeyboardButton(text="🛠 Админка")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар")],
            [KeyboardButton(text="📦 Все товары")],
            [KeyboardButton(text="💰 Изменить цену"), KeyboardButton(text="📦 Изменить остаток")],
            [KeyboardButton(text="👁 Скрыть/показать товар"), KeyboardButton(text="❌ Удалить товар")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )


def format_items(items):
    if not items:
        return "Товары не указаны"

    text = ""
    for item in items:
        text += f"• {item.get('name', 'Товар')} × {item.get('qty', 1)} — {item.get('price', 0)} ₽\n"
    return text.strip()


async def api_get_products():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/products") as response:
            if response.status == 200:
                return await response.json()
            return []


async def api_add_product(product):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/products", json=product) as response:
            return response.status in [200, 201]


async def api_update_product(product):
    async with aiohttp.ClientSession() as session:
        async with session.put(f"{API_URL}/products/{product['id']}", json=product) as response:
            return response.status in [200, 201]


async def api_delete_product(product_id):
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{API_URL}/products/{product_id}") as response:
            return response.status in [200, 201]


async def api_find_product(product_id):
    products = await api_get_products()
    for product in products:
        if str(product.get("id")) == str(product_id):
            return product
    return None


def save_order_from_webapp(message: Message, data: dict):
    orders = load_json(ORDERS_FILE, [])
    user = get_user(message.from_user.id)

    web_order = data.get("order", {})
    order_id = web_order.get("id") or int(datetime.now().timestamp())

    order = {
        "order_id": order_id,
        "telegram_id": message.from_user.id,
        "username": message.from_user.username or "",
        "name": user.get("first_name", "Клиент") if user else "Клиент",
        "phone": user.get("phone", "") if user else "",
        "status": web_order.get("status", "Оплачен"),
        "payment": web_order.get("payment", "Не указан"),
        "total": web_order.get("total", 0),
        "bonus_used": web_order.get("bonusUsed", 0),
        "bonus_earned": web_order.get("earned", 0),
        "items": web_order.get("items", []),
        "buyer": web_order.get("buyer", {}),
        "created_at": web_order.get("date", now()),
        "saved_at": now(),
    }

    orders.append(order)
    save_json(ORDERS_FILE, orders)
    return order


def save_admin_notification(data: dict):
    notifications = load_json(NOTIFICATIONS_FILE, [])

    item = {
        "id": int(datetime.now().timestamp()),
        "title": data.get("title", "Уведомление"),
        "text": data.get("text", ""),
        "created_at": now(),
    }

    notifications.append(item)
    save_json(NOTIFICATIONS_FILE, notifications)
    return item


@dp.message(CommandStart())
async def start(message: Message):
    user = get_user(message.from_user.id)

    if user and user.get("phone"):
        await message.answer(
            "Рады видеть вас снова 👋\n\n"
            "Открывайте магазин кнопкой ниже.",
            reply_markup=main_keyboard(user)
        )
        return

    await message.answer(
        "Добро пожаловать в Premium Store ✨\n\n"
        "Чтобы пользоваться магазином, поделитесь номером телефона через Telegram.",
        reply_markup=contact_keyboard()
    )


@dp.message(F.contact)
async def contact_handler(message: Message):
    if message.contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, отправьте именно свой контакт.")
        return

    user = save_user_from_contact(message)

    await message.answer(
        "Авторизация успешна ✅\n\n"
        "Теперь можно открыть магазин кнопкой ниже.",
        reply_markup=main_keyboard(user)
    )

    if user.get("role") == "admin":
        await message.answer("Вы вошли как владелец магазина 👑")

    await bot.send_message(
        ADMIN_ID,
        f"👤 Новый пользователь\n\n"
        f"Имя: {user.get('first_name')}\n"
        f"Телефон: {user.get('phone')}\n"
        f"Username: @{user.get('username') or 'нет'}\n"
        f"ID: {user.get('telegram_id')}\n"
        f"Роль: {user.get('role')}"
    )


@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = get_user(message.from_user.id)

    if not user:
        await message.answer("Сначала авторизуйтесь.", reply_markup=contact_keyboard())
        return

    await message.answer(
        f"👤 Профиль\n\n"
        f"Имя: {user.get('first_name')}\n"
        f"Телефон: {user.get('phone')}\n"
        f"Бонусы: {user.get('bonus')} баллов\n"
        f"VIP: {user.get('vip_status')}\n"
        f"Роль: {user.get('role')}",
        reply_markup=main_keyboard(user)
    )


@dp.message(F.text == "📦 Мои заказы")
async def my_orders(message: Message):
    orders = load_json(ORDERS_FILE, [])
    user_orders = [o for o in orders if o.get("telegram_id") == message.from_user.id]

    if not user_orders:
        await message.answer("У вас пока нет заказов.")
        return

    text = "📦 Ваши последние заказы:\n\n"

    for order in user_orders[-5:]:
        text += (
            f"Заказ №{order.get('order_id')}\n"
            f"Дата: {order.get('created_at')}\n"
            f"Сумма: {order.get('total')} ₽\n"
            f"Статус: {order.get('status')}\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "🔔 Уведомления")
async def notifications_handler(message: Message):
    notifications = load_json(NOTIFICATIONS_FILE, [])

    if not notifications:
        await message.answer("Уведомлений пока нет.")
        return

    text = "🔔 Последние уведомления:\n\n"

    for item in notifications[-5:]:
        text += (
            f"{item.get('title')}\n"
            f"{item.get('text')}\n"
            f"{item.get('created_at')}\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    settings = load_json(SETTINGS_FILE, {})
    support_username = settings.get("support", "@zzleedzz")
    await message.answer(f"Поддержка: {support_username}")


@dp.message(F.web_app_data)
async def web_app_data_handler(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        await message.answer(f"Ошибка чтения данных Mini App: {e}")
        return

    data_type = data.get("type")

    if data_type == "new_order":
        order = save_order_from_webapp(message, data)
        buyer = order.get("buyer", {})

        admin_text = (
            f"🛍 НОВЫЙ ЗАКАЗ №{order.get('order_id')}\n\n"
            f"Клиент: {order.get('name')}\n"
            f"Телефон профиля: {order.get('phone')}\n"
            f"Username: @{order.get('username') or 'нет'}\n"
            f"ID: {order.get('telegram_id')}\n\n"
            f"Данные покупателя:\n"
            f"Имя: {buyer.get('name', '')}\n"
            f"Фамилия: {buyer.get('surname', '')}\n"
            f"Телефон: {buyer.get('phone', '')}\n"
            f"Адрес ПВЗ: {buyer.get('address', '')}\n\n"
            f"Оплата: {order.get('payment')}\n"
            f"Статус: {order.get('status')}\n\n"
            f"Товары:\n{format_items(order.get('items', []))}\n\n"
            f"Списано бонусами: {order.get('bonus_used')} ₽\n"
            f"Начислено бонусов: {order.get('bonus_earned')}\n"
            f"Итого: {order.get('total')} ₽"
        )

        await bot.send_message(ADMIN_ID, admin_text)

        user = get_user(message.from_user.id)
        await message.answer(
            f"Заказ №{order.get('order_id')} принят ✅\n\n"
            f"Статус: {order.get('status')}\n"
            "Данные отправлены владельцу магазина.",
            reply_markup=main_keyboard(user) if user else None
        )
        return

    if data_type == "admin_notification":
        notification = save_admin_notification(data)

        await bot.send_message(
            ADMIN_ID,
            f"🔔 Новое уведомление создано\n\n"
            f"{notification.get('title')}\n"
            f"{notification.get('text')}\n"
            f"{notification.get('created_at')}"
        )

        await message.answer("Уведомление сохранено ✅")
        return

    await message.answer("Данные Mini App получены.")


@dp.message(F.text == "/admin_orders")
async def admin_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    orders = load_json(ORDERS_FILE, [])

    if not orders:
        await message.answer("Заказов пока нет.")
        return

    text = "📦 Последние заказы:\n\n"

    for order in orders[-10:]:
        text += (
            f"№{order.get('order_id')} | {order.get('status')}\n"
            f"{order.get('name')} | {order.get('phone')}\n"
            f"Сумма: {order.get('total')} ₽\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "🛠 Админка")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await message.answer(
        "🛠 Админ-панель\n\nВыберите действие:",
        reply_markup=admin_keyboard()
    )


@dp.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    await message.answer(
        "Главное меню:",
        reply_markup=main_keyboard(user) if user else contact_keyboard()
    )


@dp.message(F.text == "➕ Добавить товар")
async def add_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await state.set_state(AddProduct.name)
    await message.answer("Введите название товара:")


@dp.message(AddProduct.name)
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.category)
    await message.answer("Введите категорию: Новинки или Популярные")


@dp.message(AddProduct.category)
async def add_product_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Введите цену товара цифрами:")


@dp.message(AddProduct.price)
async def add_product_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите цену только цифрами.")
        return

    await state.update_data(price=int(message.text))
    await state.set_state(AddProduct.old_price)
    await message.answer("Введите старую цену для скидки или 0:")


@dp.message(AddProduct.old_price)
async def add_product_old_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите старую цену цифрами или 0.")
        return

    await state.update_data(oldPrice=int(message.text) if message.text != "0" else "")
    await state.set_state(AddProduct.stock)
    await message.answer("Введите остаток товара цифрами:")


@dp.message(AddProduct.stock)
async def add_product_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите остаток только цифрами.")
        return

    await state.update_data(stock=int(message.text))
    await state.set_state(AddProduct.desc)
    await message.answer("Введите описание товара:")


@dp.message(AddProduct.desc)
async def add_product_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(AddProduct.image)
    await message.answer("Вставьте ссылку на картинку товара:")


@dp.message(AddProduct.image)
async def add_product_image(message: Message, state: FSMContext):
    data = await state.get_data()

    product = {
        "id": int(datetime.now().timestamp() * 1000),
        "name": data.get("name"),
        "category": data.get("category", "Новинки"),
        "price": data.get("price", 0),
        "oldPrice": data.get("oldPrice", ""),
        "stock": data.get("stock", 0),
        "desc": data.get("desc", ""),
        "image": message.text,
        "active": True
    }

    ok = await api_add_product(product)

    if ok:
        await message.answer(
            f"✅ Товар добавлен:\n\n"
            f"ID: {product['id']}\n"
            f"{product['name']}\n"
            f"Цена: {product['price']} ₽\n"
            f"Категория: {product['category']}",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("Ошибка добавления товара на сервер.")

    await state.clear()


@dp.message(F.text == "📦 Все товары")
async def all_products(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    products = await api_get_products()

    if not products:
        await message.answer("Товаров пока нет.")
        return

    text = "📦 Товары:\n\n"
    for p in products[:15]:
        status = "✅ показывается" if p.get("active") else "🙈 скрыт"
        text += (
            f"ID: {p.get('id')}\n"
            f"{p.get('name')}\n"
            f"Цена: {p.get('price')} ₽\n"
            f"Остаток: {p.get('stock')}\n"
            f"Статус: {status}\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "💰 Изменить цену")
async def edit_price_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await state.set_state(EditProduct.product_id)
    await state.update_data(action="price")
    await message.answer("Введите ID товара, у которого нужно изменить цену:")


@dp.message(F.text == "📦 Изменить остаток")
async def edit_stock_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await state.set_state(EditProduct.product_id)
    await state.update_data(action="stock")
    await message.answer("Введите ID товара, у которого нужно изменить остаток:")


@dp.message(EditProduct.product_id)
async def edit_product_choose(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите ID только цифрами.")
        return

    product = await api_find_product(message.text)

    if not product:
        await message.answer("Товар с таким ID не найден.")
        await state.clear()
        return

    data = await state.get_data()
    action = data.get("action")

    await state.update_data(product=product)

    if action == "price":
        await state.set_state(EditProduct.price)
        await message.answer(
            f"Товар: {product.get('name')}\n"
            f"Текущая цена: {product.get('price')} ₽\n\n"
            "Введите новую цену:"
        )
    else:
        await state.set_state(EditProduct.stock)
        await message.answer(
            f"Товар: {product.get('name')}\n"
            f"Текущий остаток: {product.get('stock')}\n\n"
            "Введите новый остаток:"
        )


@dp.message(EditProduct.price)
async def edit_product_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите цену только цифрами.")
        return

    data = await state.get_data()
    product = data.get("product")
    product["price"] = int(message.text)

    ok = await api_update_product(product)

    if ok:
        await message.answer(
            f"✅ Цена изменена\n\n"
            f"{product.get('name')}\n"
            f"Новая цена: {product.get('price')} ₽",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("Ошибка обновления цены.")

    await state.clear()


@dp.message(EditProduct.stock)
async def edit_product_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите остаток только цифрами.")
        return

    data = await state.get_data()
    product = data.get("product")
    product["stock"] = int(message.text)

    ok = await api_update_product(product)

    if ok:
        await message.answer(
            f"✅ Остаток изменён\n\n"
            f"{product.get('name')}\n"
            f"Новый остаток: {product.get('stock')}",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("Ошибка обновления остатка.")

    await state.clear()


@dp.message(F.text == "👁 Скрыть/показать товар")
async def toggle_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await state.set_state(ToggleProduct.product_id)
    await message.answer("Введите ID товара, который нужно скрыть или показать:")


@dp.message(ToggleProduct.product_id)
async def toggle_product_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите ID только цифрами.")
        return

    product = await api_find_product(message.text)

    if not product:
        await message.answer("Товар с таким ID не найден.")
        await state.clear()
        return

    product["active"] = not product.get("active", True)

    ok = await api_update_product(product)

    if ok:
        status = "показывается в каталоге ✅" if product["active"] else "скрыт из каталога 🙈"
        await message.answer(
            f"✅ Статус изменён\n\n"
            f"{product.get('name')}\n"
            f"Теперь товар: {status}",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("Ошибка изменения статуса.")

    await state.clear()


@dp.message(F.text == "❌ Удалить товар")
async def delete_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ закрыт.")
        return

    await state.set_state(DeleteProduct.product_id)
    await message.answer("Введите ID товара, который нужно удалить:")


@dp.message(DeleteProduct.product_id)
async def delete_product_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите ID только цифрами.")
        return

    product = await api_find_product(message.text)

    if not product:
        await message.answer("Товар с таким ID не найден.")
        await state.clear()
        return

    ok = await api_delete_product(message.text)

    if ok:
        await message.answer(
            f"✅ Товар удалён:\n\n{product.get('name')}",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("Ошибка удаления товара.")

    await state.clear()


@dp.message()
async def other(message: Message):
    user = get_user(message.from_user.id)

    if user and user.get("phone"):
        await message.answer("Выберите действие ниже 👇", reply_markup=main_keyboard(user))
    else:
        await message.answer("Сначала авторизуйтесь.", reply_markup=contact_keyboard())


async def main():
    ensure_files()
    print("Premium Store bot started...")
    await dp.start_polling(bot)


threading.Thread(target=run_health_server, daemon=True).start()
