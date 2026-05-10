import asyncio
import json
import os
import threading
from flask import Flask
from datetime import datetime
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

TOKEN = "8640152586:AAER3Gh8464mOktlneUPO3RcQ9dw8YvzRQU"
ADMIN_ID = 588097726
MINI_APP_URL = "https://singular-mooncake-c8c1b8.netlify.app"

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
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛍 Открыть Premium Store",
                    web_app=WebAppInfo(url=mini_app_link(user))
                )
            ],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📦 Мои заказы")],
            [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="📞 Поддержка")]
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


if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main())
