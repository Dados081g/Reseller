import os
import json
import logging
import requests
from datetime import datetime
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8556473299:AAG3BjxR6YbP6PZJ8mCrmOQ7pmlrrTCZq6c"
OWNER_ID = 5000488732
API_KEY = "102+ox3PbiE9HuaRfraS2Qy4i+k7h3tfOXmS4ZNTyew=_MDK9VHe5vyXvnx0wLHbfhJZY56cgpzxlpljswT7fKL8Pa0Y5fkr05Qvh8PYCWOHnjsr"
API_URL = "https://modkey.host/api/v1/action"

DATA_FILE = "void_panel_data.json"

(
    AWAIT_ADMIN_ID, 
    AWAIT_BALANCE_ID,
    AWAIT_BALANCE_AMOUNT,
    AWAIT_KEY_DAYS,
    AWAIT_KEY_DEVICES,
    AWAIT_KEY_TYPE,
    AWAIT_KEY_COUNT,
    AWAIT_KEY_INFO,
    AWAIT_BLOCK_KEY,
    AWAIT_UNBLOCK_KEY,
    AWAIT_RESET_KEY,
    AWAIT_REMOVE_ADMIN_ID,
    AWAIT_DEDUCT_ID,
    AWAIT_DEDUCT_AMOUNT,
) = range(14)


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"admins": {}, "pending_action": {}}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def modkey_request(method: str, extra: dict = None):
    payload = {"api_key": API_KEY, "method": method}
    if extra:
        payload.update(extra)
    try:
        r = requests.post(API_URL, data=payload, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": False, "reason": str(e)}


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    data = load_data()
    return str(user_id) in data.get("admins", {})


def owner_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        uid = update.effective_user.id
        if not is_owner(uid):
            await update.message.reply_text("❌ Доступ запрещён.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_or_owner(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        uid = update.effective_user.id
        if not (is_owner(uid) or is_admin(uid)):
            await update.message.reply_text("❌ Доступ запрещён.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def get_user_balance(user_id: int) -> float:
    data = load_data()
    return float(data.get("admins", {}).get(str(user_id), {}).get("balance", 0))


def set_user_balance(user_id: int, amount: float):
    data = load_data()
    admins = data.setdefault("admins", {})
    uid = str(user_id)
    if uid in admins:
        admins[uid]["balance"] = round(amount, 2)
        save_data(data)


KEY_PRICES = {
    "5h":    500,
    "1d":    30,
    "3d":    55,
    "7d":    150,
    "14d":   280,
    "30d":   550,
    "60d":   799,
    "25000": 9999,
}

DURATION_LABELS = {
    "5h":    "5 Hours",
    "1d":    "1 Day",
    "3d":    "3 Days",
    "7d":    "7 Days",
    "14d":   "14 Days",
    "30d":   "30 Days",
    "60d":   "60 Days",
    "25000": "LIFETIME",
}

DAYS_MAP = {
    "5h":    0,
    "1d":    1,
    "3d":    3,
    "7d":    7,
    "14d":   14,
    "30d":   30,
    "60d":   60,
    "25000": 25000,
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_owner(uid):
        role = "👑 Владелец"
    elif is_admin(uid):
        role = "🛡 Администратор"
    else:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return

    balance_line = ""
    if is_admin(uid) and not is_owner(uid):
        bal = get_user_balance(uid)
        balance_line = f"\n💰 Ваш баланс: <b>${bal}</b>"

    keyboard = build_main_menu(uid)
    await update.message.reply_text(
        f"🎮 <b>Void Panel Bot</b>\n"
        f"Роль: {role}{balance_line}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


def build_main_menu(uid: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔑 Создать ключ", callback_data="create_key")],
        [InlineKeyboardButton("🔍 Инфо о ключе", callback_data="key_info")],
        [InlineKeyboardButton("📋 Все ключи", callback_data="all_keys")],
        [InlineKeyboardButton("🚫 Заблокировать ключ", callback_data="block_key"),
         InlineKeyboardButton("✅ Разблокировать", callback_data="unblock_key")],
        [InlineKeyboardButton("♻️ Сбросить HWID", callback_data="reset_hwid")],
    ]
    if is_owner(uid):
        buttons.append([InlineKeyboardButton("👤 Управление админами", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"[CALLBACK] uid={query.from_user.id} data={query.data}")
    await query.answer()
    uid = query.from_user.id

    if not (is_owner(uid) or is_admin(uid)):
        await query.edit_message_text("❌ Доступ запрещён.")
        return

    data_val = query.data

    if data_val == "create_key":
        context.user_data.clear()
        keyboard = []
        for key, label in DURATION_LABELS.items():
            price = KEY_PRICES[key]
            keyboard.append([InlineKeyboardButton(
                f"{label} — ${price}",
                callback_data=f"dur_{key}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.edit_message_text(
            "🕐 Выберите срок ключа:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data_val.startswith("dur_"):
        dur = data_val[4:]
        context.user_data["duration"] = dur
        keyboard = [
            [InlineKeyboardButton("APK / LOADER", callback_data="type_APK")],
            [InlineKeyboardButton("INJECTOR / LOADER", callback_data="type_INJECTOR")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]
        await query.edit_message_text(
            f"✅ Срок: <b>{DURATION_LABELS[dur]}</b>\n\n🔧 Выберите тип ключа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data_val.startswith("type_"):
        ktype = data_val[5:]
        context.user_data["key_type"] = ktype
        keyboard = []
        for n in [1, 2, 3, 5, 10]:
            keyboard.append([InlineKeyboardButton(f"{n} шт.", callback_data=f"cnt_{n}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.edit_message_text(
            f"✅ Тип: <b>{ktype}</b>\n\n📦 Количество ключей:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data_val.startswith("cnt_"):
        count = int(data_val[4:])
        context.user_data["count"] = count
        keyboard = []
        for d in [1, 2, 3, 5]:
            keyboard.append([InlineKeyboardButton(f"{d} устройств", callback_data=f"dev_{d}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.edit_message_text(
            f"✅ Количество: <b>{count}</b>\n\n📱 Максимум устройств на ключ:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data_val.startswith("dev_"):
        devices = int(data_val[4:])
        context.user_data["devices"] = devices
        dur = context.user_data["duration"]
        ktype = context.user_data["key_type"]
        count = context.user_data["count"]
        price_per = KEY_PRICES[dur]
        total = price_per * count

        if not is_owner(uid):
            bal = get_user_balance(uid)
            if bal < total:
                await query.edit_message_text(
                    f"❌ Недостаточно баланса.\n"
                    f"Требуется: <b>${total}</b>\n"
                    f"Ваш баланс: <b>${bal}</b>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
                    ]])
                )
                return

        await query.edit_message_text("⏳ Генерирую ключи...")

        result = modkey_request("create-key", {
            "days": DAYS_MAP[dur],
            "devices": devices,
            "type": ktype,
            "count": count,
        })

        if result.get("status"):
            if not is_owner(uid):
                bal = get_user_balance(uid)
                set_user_balance(uid, bal - total)
                new_bal = bal - total
                bal_line = f"\n💰 Остаток баланса: <b>${new_bal}</b>"
            else:
                bal_line = ""

            d = result["data"]
            if count == 1:
                key_text = f"<code>{d['key']}</code>"
            else:
                key_text = "\n".join([f"<code>{k}</code>" for k in d["keys"]])

            await query.edit_message_text(
                f"✅ <b>Ключи созданы!</b>\n\n"
                f"🕐 Срок: <b>{DURATION_LABELS[dur]}</b>\n"
                f"🔧 Тип: <b>{ktype}</b>\n"
                f"📱 Устройств: <b>{devices}</b>\n"
                f"💵 Цена: <b>${price_per} × {count} = ${total}</b>{bal_line}\n\n"
                f"🔑 Ключи:\n{key_text}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await query.edit_message_text(
                f"❌ Ошибка: {result.get('reason', 'Неизвестная ошибка')}\nКод: {result.get('code')}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
                ]])
            )

    elif data_val == "key_info":
        await query.edit_message_text(
            "🔍 Введите ключ для проверки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "key_info"

    elif data_val == "all_keys":
        await query.edit_message_text("⏳ Загружаю список ключей...")
        result = modkey_request("get-all-keys")
        if result.get("status"):
            keys = result["data"]["keys"]
            if not keys:
                text = "📭 Ключей нет."
            else:
                lines = []
                for k in keys[:30]:
                    status = "✅" if k["status"] == "1" else "🚫"
                    active = "🟢" if k["active"] == "1" else "⚪"
                    lines.append(
                        f"{status}{active} <code>{k['user_key']}</code> | {k['duration']}d | {k['key_type']}"
                    )
                text = f"📋 <b>Ключи ({len(keys)} шт.):</b>\n\n" + "\n".join(lines)
                if len(keys) > 30:
                    text += f"\n\n<i>...и ещё {len(keys)-30}</i>"
        else:
            text = f"❌ Ошибка: {result.get('reason')}"
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ]])
        )

    elif data_val == "block_key":
        await query.edit_message_text(
            "🚫 Введите ключ для блокировки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "block_key"

    elif data_val == "unblock_key":
        await query.edit_message_text(
            "✅ Введите ключ для разблокировки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "unblock_key"

    elif data_val == "reset_hwid":
        await query.edit_message_text(
            "♻️ Введите ключ для сброса HWID:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "reset_hwid"

    elif data_val == "admin_panel":
        if not is_owner(uid):
            await query.edit_message_text("❌ Только для владельца.")
            return
        db = load_data()
        admins = db.get("admins", {})
        if admins:
            lines = [f"👤 <code>{aid}</code> — {info.get('username','?')} | 💰${info.get('balance',0)}"
                     for aid, info in admins.items()]
            admin_text = "\n".join(lines)
        else:
            admin_text = "Нет администраторов."

        keyboard = [
            [InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Удалить админа", callback_data="remove_admin")],
            [InlineKeyboardButton("💰 Пополнить баланс", callback_data="add_balance")],
            [InlineKeyboardButton("💸 Снять баланс", callback_data="deduct_balance")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            f"👥 <b>Администраторы:</b>\n\n{admin_text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data_val == "add_admin":
        if not is_owner(uid):
            return
        await query.edit_message_text(
            "👤 Введите Telegram ID нового администратора:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "add_admin"

    elif data_val == "remove_admin":
        if not is_owner(uid):
            return
        await query.edit_message_text(
            "👤 Введите Telegram ID администратора для удаления:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "remove_admin"

    elif data_val == "add_balance":
        if not is_owner(uid):
            return
        await query.edit_message_text(
            "💰 Введите Telegram ID и сумму через пробел:\nПример: <code>123456789 500</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "add_balance"

    elif data_val == "deduct_balance":
        if not is_owner(uid):
            return
        await query.edit_message_text(
            "💸 Введите Telegram ID и сумму для снятия через пробел:\nПример: <code>123456789 100</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )
        context.user_data["await"] = "deduct_balance"

    elif data_val == "main_menu":
        keyboard = build_main_menu(uid)
        if is_owner(uid):
            role = "👑 Владелец"
            bal_line = ""
        else:
            role = "🛡 Администратор"
            bal = get_user_balance(uid)
            bal_line = f"\n💰 Ваш баланс: <b>${bal}</b>"
        await query.edit_message_text(
            f"🎮 <b>Void Panel Bot</b>\nРоль: {role}{bal_line}\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif data_val == "cancel":
        context.user_data.clear()
        keyboard = build_main_menu(uid)
        await query.edit_message_text(
            "❌ Отменено.\n\nВыберите действие:",
            reply_markup=keyboard
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not (is_owner(uid) or is_admin(uid)):
        return

    action = context.user_data.get("await")
    text = update.message.text.strip()

    if action == "key_info":
        result = modkey_request("get-key-info", {"key": text})
        if result.get("status"):
            d = result["data"]
            status = "✅ Активен" if d["status"] == "1" else "🚫 Заблокирован"
            active = "🟢 Используется" if d["active"] == "1" else "⚪ Не активирован"
            msg = (
                f"🔑 <b>Информация о ключе</b>\n\n"
                f"Ключ: <code>{d['key']}</code>\n"
                f"Статус: {status}\n"
                f"Активация: {active}\n"
                f"Срок: <b>{d['duration']} дней</b>\n"
                f"Истекает: <b>{d['expired_date']}</b>\n"
                f"Устройств: <b>{d['devices'] or '0'}/{d['max_devices']}</b>\n"
                f"Тип: <b>{d['key_type']}</b>\n"
                f"Создал: <b>{d['registrator']}</b>"
            )
        else:
            msg = f"❌ Ошибка: {result.get('reason')}"
        await update.message.reply_text(
            msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ]])
        )
        context.user_data.clear()

    elif action == "block_key":
        result = modkey_request("edit-key-status", {"key": text, "type": "block"})
        if result.get("status"):
            await update.message.reply_text(
                f"🚫 Ключ <code>{text}</code> заблокирован.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {result.get('reason')}")
        context.user_data.clear()

    elif action == "unblock_key":
        result = modkey_request("edit-key-status", {"key": text, "type": "unblock"})
        if result.get("status"):
            await update.message.reply_text(
                f"✅ Ключ <code>{text}</code> разблокирован.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {result.get('reason')}")
        context.user_data.clear()

    elif action == "reset_hwid":
        result = modkey_request("reset-key-hwid", {"key": text})
        if result.get("status"):
            await update.message.reply_text(
                f"♻️ HWID ключа <code>{text}</code> сброшен.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {result.get('reason')}")
        context.user_data.clear()

    elif action == "add_admin":
        if not is_owner(uid):
            return
        try:
            new_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Неверный ID.")
            return
        db = load_data()
        admins = db.setdefault("admins", {})
        if str(new_id) in admins:
            await update.message.reply_text("⚠️ Этот пользователь уже является администратором.")
        else:
            admins[str(new_id)] = {"username": str(new_id), "balance": 0}
            save_data(db)
            await update.message.reply_text(
                f"✅ Администратор <code>{new_id}</code> добавлен.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👥 Панель админов", callback_data="admin_panel")
                ]])
            )
        context.user_data.clear()

    elif action == "remove_admin":
        if not is_owner(uid):
            return
        try:
            rem_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Неверный ID.")
            return
        db = load_data()
        admins = db.setdefault("admins", {})
        if str(rem_id) not in admins:
            await update.message.reply_text("⚠️ Такого администратора нет.")
        else:
            del admins[str(rem_id)]
            save_data(db)
            await update.message.reply_text(
                f"✅ Администратор <code>{rem_id}</code> удалён.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👥 Панель админов", callback_data="admin_panel")
                ]])
            )
        context.user_data.clear()

    elif action == "add_balance":
        if not is_owner(uid):
            return
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Формат: <ID> <сумма>")
            return
        try:
            target_id = int(parts[0])
            amount = float(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Неверный формат.")
            return
        db = load_data()
        if str(target_id) not in db.get("admins", {}):
            await update.message.reply_text("❌ Администратор не найден.")
            context.user_data.clear()
            return
        old_bal = float(db["admins"][str(target_id)].get("balance", 0))
        new_bal = round(old_bal + amount, 2)
        db["admins"][str(target_id)]["balance"] = new_bal
        save_data(db)
        await update.message.reply_text(
            f"✅ Баланс <code>{target_id}</code> пополнен.\n"
            f"Было: <b>${old_bal}</b> → Стало: <b>${new_bal}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👥 Панель админов", callback_data="admin_panel")
            ]])
        )
        context.user_data.clear()

    elif action == "deduct_balance":
        if not is_owner(uid):
            return
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Формат: <ID> <сумма>")
            return
        try:
            target_id = int(parts[0])
            amount = float(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Неверный формат.")
            return
        db = load_data()
        if str(target_id) not in db.get("admins", {}):
            await update.message.reply_text("❌ Администратор не найден.")
            context.user_data.clear()
            return
        old_bal = float(db["admins"][str(target_id)].get("balance", 0))
        new_bal = round(old_bal - amount, 2)
        db["admins"][str(target_id)]["balance"] = new_bal
        save_data(db)
        await update.message.reply_text(
            f"💸 Баланс <code>{target_id}</code> уменьшен.\n"
            f"Было: <b>${old_bal}</b> → Стало: <b>${new_bal}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👥 Панель админов", callback_data="admin_panel")
            ]])
        )
        context.user_data.clear()


async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not (is_owner(uid) or is_admin(uid)):
        return
    result = modkey_request("get-me")
    if result.get("status"):
        d = result["data"]
        soft = d.get("soft", {})
        msg = (
            f"👤 <b>Аккаунт Modkey</b>\n\n"
            f"ID: <code>{d['id']}</code>\n"
            f"Username: <b>{d['username']}</b>\n"
            f"Баланс: <b>${d['balance']}</b>\n"
            f"VIP: <b>{'Да' if d['VIP'] != '0' else 'Нет'}</b>\n\n"
            f"🔧 Софт: <b>{soft.get('name')}</b>\n"
            f"Статус: <b>{'On' if soft.get('soft_status') == '1' else 'Off'}</b>"
        )
    else:
        msg = f"❌ Ошибка: {result.get('reason')}"
    await update.message.reply_text(msg, parse_mode="HTML")


TEXT_BUTTON_MAP = {
    "🔑 Создать ключ": "create_key",
    "🔍 Инфо о ключе": "key_info",
    "📋 Все ключи": "all_keys",
    "🚫 Заблокировать ключ": "block_key",
    "✅ Разблокировать": "unblock_key",
    "♻️ Сбросить HWID": "reset_hwid",
    "👤 Управление админами": "admin_panel",
    "💰 Мой баланс": "my_balance",
    "🏠 Главное меню": "main_menu",
    "👥 Управление доступом": "admin_panel",
}


async def reply_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not (is_owner(uid) or is_admin(uid)):
        return

    text = update.message.text.strip()

    if context.user_data.get("await"):
        await text_handler(update, context)
        return

    cb = TEXT_BUTTON_MAP.get(text)
    if cb == "my_balance":
        if is_owner(uid):
            await update.message.reply_text("👑 У владельца нет лимита баланса.")
        else:
            bal = get_user_balance(uid)
            await update.message.reply_text(f"💰 Ваш баланс: <b>${bal}</b>", parse_mode="HTML")
        return

    if cb:
        class FakeQuery:
            def __init__(self, data, user, message):
                self.data = data
                self.from_user = user
                self.message = message
            async def answer(self): pass
            async def edit_message_text(self, text, **kwargs):
                await update.message.reply_text(text, **kwargs)

        fake_update = Update.__new__(Update)
        fake_update._effective_user = update.effective_user
        fake_update._effective_message = update.message
        fake_update.callback_query = FakeQuery(cb, update.effective_user, update.message)
        await menu_callback(fake_update, context)
        return

    await text_handler(update, context)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CallbackQueryHandler(menu_callback), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_button_handler), group=1)

    logger.info("VoidPanel Bot запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
