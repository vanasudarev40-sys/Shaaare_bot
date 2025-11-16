import telebot
from telebot import types
import threading
import json
import os
from datetime import datetime, timedelta
import time
import traceback

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN", "7945043414:AAFsWTcwFPWM-GH8-keyxdAf9oqQNt6FJlo")
ADMINS = [8133757512]
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN)
data_lock = threading.Lock()

PRESET_TIMES = [f"{h:02d}:00" for h in range(8, 21)]
RU_WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

WELCOME_TEXT = (
    "👋 Привет! Я — автоматический помощник для записи на приём к специалистам. Работаю 24/7.\n\n"
    "Я умею:\n"
    "- 📅 Записывать вас на удобное время;\n"
    "- 🔔 Напоминать за час до приёма;\n"
    "- 📨 Принимать запросы и предложения для админа;\n"
    "- ✉️ Пересылать сообщения специалистам — админ ответит вам напрямую;\n"
    "- ⚙️ Управлять расписанием через админ‑панель (для админов).\n\n"
    "Нажмите «🔘 Начать» или отправьте /start, чтобы открыть меню.\n"
    "Если нужно — напишите «Запрос» или «Предложение», либо выберите специалиста из списка.\n\n"
    "✨ Я работаю круглосуточно, чтобы сделать запись проще и удобнее для вас!"
)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "specialists": ["Иванов Иван Иванович", "Петров Пётр Петрович", "Сидорова Анна Сергеевна"],
            "schedule": {},
            "records": {},
            "messages": [],
            "next_message_id": 1
        }, f, ensure_ascii=False, indent=2)

def load_data():
    with data_lock:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

def save_data(data):
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def safe_edit_message(chat_id, message_id, text, reply_markup=None):
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)
    except Exception as e:
        print("safe_edit_message failed:", e)
        try:
            bot.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception as e2:
            print("safe_edit fallback failed:", e2)

def get_username(user):
    if getattr(user, "username", None):
        return f"@{user.username}"
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    return (first + " " + last).strip() or f"id{user.id}"

def remove_reply_kb():
    return types.ReplyKeyboardRemove()

def _build_admin_notify_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📨 Посмотреть", callback_data="admin_view_messages"),
           types.InlineKeyboardButton("🗑 Удалить", callback_data="del_notify"))
    return kb

def set_admin_notification_count(admin_id, count, data=None):
    if data is None:
        data = load_data()
    admin_notifications = data.setdefault("admin_notifications", {})
    key = str(admin_id)
    entry = admin_notifications.get(key)
    text = f"У вас {count} новых сообщений." if count > 0 else "Нет новых сообщений."
    kb = _build_admin_notify_kb()
    try:
        previous_count = 0
        if entry:
            previous_count = entry.get("count", 0)

        try:
            if count > previous_count and count > 0:
                alert_text = f"🔔 У вас {count} новых сообщений. Нажмите 'Посмотреть'."
                try:
                    bot.send_message(admin_id, alert_text, reply_markup=kb)
                except Exception:
                    print("failed to send admin alert", admin_id, traceback.format_exc())
        except Exception:
            print("failed to check previous_count", traceback.format_exc())

        if entry and entry.get("msg_id"):
            try:
                bot.edit_message_text(chat_id=admin_id, message_id=entry["msg_id"], text=text, reply_markup=kb if count>0 else None)
                if count <= 0:
                    admin_notifications.pop(key, None)
                else:
                    admin_notifications[key]["count"] = count
            except Exception:
                try:
                    msg = bot.send_message(admin_id, text, reply_markup=kb if count>0 else None)
                    if count > 0:
                        admin_notifications[key] = {"msg_id": msg.message_id, "count": count}
                    else:
                        admin_notifications.pop(key, None)
                except Exception:
                    print("failed to send fallback admin notify", admin_id, traceback.format_exc())
        else:
            if count > 0:
                try:
                    msg = bot.send_message(admin_id, text, reply_markup=kb)
                    admin_notifications[key] = {"msg_id": msg.message_id, "count": count}
                except Exception:
                    print("failed to send admin notify new", admin_id, traceback.format_exc())
    except Exception:
        print("set_admin_notification_count failed for", admin_id, traceback.format_exc())
    save_data(data)

def increment_admin_notifications_for_all(data=None):
    if data is None:
        data = load_data()
    msgs_count = len(data.get("messages", []))
    for adm in ADMINS:
        set_admin_notification_count(adm, msgs_count, data)

def main_keyboard(user_id=None):
    data = load_data()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("🔘 Начать"), types.KeyboardButton("Запрос"))
    kb.add(types.KeyboardButton("Предложение"))
    for idx, spec in enumerate(data["specialists"]):
        kb.add(types.KeyboardButton(spec))
    kb.add(types.KeyboardButton("📋 Мои записи"))
    if user_id in ADMINS:
        kb.add(types.KeyboardButton("⚙️ Админ панель"))
    return kb

def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Все записи")
    kb.add("💬 Сообщения пользователей")
    kb.add("⏰ Управление временем")
    kb.add("👥 Управление специалистов")
    kb.add("🔙 На главную")
    return kb

def specialists_manage_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Добавить специалиста", "Удалить специалиста", "Переименовать специалиста")
    kb.add("🔙 На главную")
    return kb

pending_action = {}

@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    pending_action.pop(chat_id, None)
    bot.send_message(chat_id, WELCOME_TEXT, reply_markup=main_keyboard(user_id))

@bot.message_handler(func=lambda m: True)
def all_text_handler(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        text = (message.text or "").strip()
        data = load_data()

        if chat_id in pending_action:
            info = pending_action[chat_id]
            action = info.get("action")

            if action == "spec_add" and user_id in ADMINS:
                name = text
                if name and name not in data["specialists"]:
                    data["specialists"].append(name)
                    save_data(data)
                    bot.send_message(chat_id, f"✅ Добавлен специалист: {name}", reply_markup=specialists_manage_keyboard())
                else:
                    bot.send_message(chat_id, "Имя пустое или уже существует.", reply_markup=specialists_manage_keyboard())
                pending_action.pop(chat_id, None)
                return

            if action == "spec_remove" and user_id in ADMINS:
                name = text
                if name in data["specialists"]:
                    data["specialists"].remove(name)
                    data.get("schedule", {}).pop(name, None)
                    recs_all = data.get("records", {})
                    for uid in list(recs_all.keys()):
                        recs = recs_all[uid]
                        new_recs = [r for r in recs if r.get("spec") != name]
                        if new_recs:
                            data["records"][uid] = new_recs
                        else:
                            data["records"].pop(uid, None)
                    save_data(data)
                    bot.send_message(chat_id, f"❌ Специалист '{name}' удалён, связанные записи и расписание удалены.", reply_markup=specialists_manage_keyboard())
                else:
                    bot.send_message(chat_id, "Специалист с таким именем не найден.", reply_markup=specialists_manage_keyboard())
                pending_action.pop(chat_id, None)
                return

            if action == "spec_rename" and user_id in ADMINS:
                old_name = info.get("old_name")
                new_name = text
                if old_name and old_name in data["specialists"] and new_name:
                    idx = data["specialists"].index(old_name)
                    data["specialists"][idx] = new_name
                    if old_name in data.get("schedule", {}):
                        data["schedule"][new_name] = data["schedule"].pop(old_name)
                    for uid, recs in data.get("records", {}).items():
                        for r in recs:
                            if r.get("spec") == old_name:
                                r["spec"] = new_name
                    save_data(data)
                    bot.send_message(chat_id, f"✏️ '{old_name}' переименован в '{new_name}'", reply_markup=specialists_manage_keyboard())
                else:
                    bot.send_message(chat_id, "Ошибка: старое имя не найдено или новое имя пустое.", reply_markup=specialists_manage_keyboard())
                pending_action.pop(chat_id, None)
                return

            if action in ("user_request", "user_suggest"):
                tag = "запрос" if action == "user_request" else "предложение"
                mid = data.get("next_message_id", 1)
                username = get_username(message.from_user)
                msg_obj = {"id": mid, "from_id": user_id, "from_username": username, "tag": tag, "text": text, "ts": datetime.now().isoformat()}
                data.setdefault("messages", []).append(msg_obj)
                data["next_message_id"] = mid + 1
                save_data(data)
                bot.send_message(chat_id, f"Ваше сообщение сохранено {tag}:\n\n{text}", reply_markup=main_keyboard(user_id))
                for adm in ADMINS:
                    try:
                        data = load_data()
                        set_admin_notification_count(adm, len(data.get("messages", [])), data)
                    except Exception:
                        print("notify admin failed", adm, traceback.format_exc())
                pending_action.pop(chat_id, None)
                return

            if action == "writing_message":
                spec = info.get("spec")
                username = get_username(message.from_user)
                mid = data.get("next_message_id", 1)
                msg_obj = {
                    "id": mid,
                    "from_id": user_id,
                    "from_username": username,
                    "tag": "сообщение_специалисту",
                    "spec": spec,
                    "text": text,
                    "ts": datetime.now().isoformat()
                }
                data.setdefault("messages", []).append(msg_obj)
                data["next_message_id"] = mid + 1
                save_data(data)
                bot.send_message(chat_id, f"✉️ Ваше сообщение специалисту '{spec}' отправлено администраторам. Админ постарается ответить как можно скорее.", reply_markup=main_keyboard(user_id))
                for adm in ADMINS:
                    try:
                        data = load_data()
                        set_admin_notification_count(adm, len(data.get("messages", [])), data)
                    except Exception:
                        print("send to admin failed", adm, traceback.format_exc())
                pending_action.pop(chat_id, None)
                return

            if action == "admin_reply" and user_id in ADMINS:
                target_uid = info.get("target_user_id")
                reply_mid = info.get("reply_mid")
                reply_text = text
                if not target_uid:
                    bot.send_message(chat_id, "Не удалось определить пользователя для ответа.", reply_markup=main_keyboard(user_id))
                    pending_action.pop(chat_id, None)
                    return
                try:
                    sender_name = get_username(message.from_user)
                    bot.send_message(int(target_uid), f"✉️ Ответ администратора {sender_name}:\n\n{reply_text}")
                except Exception:
                    bot.send_message(chat_id, "Не удалось отправить сообщение пользователю.", reply_markup=main_keyboard(user_id))
                    pending_action.pop(chat_id, None)
                    return
                msgs = data.get("messages", [])
                for m in msgs:
                    if int(m.get("id", -1)) == int(reply_mid):
                        m["answered"] = True
                        m["answered_by"] = user_id
                        m["answered_ts"] = datetime.now().isoformat()
                        break
                save_data(data)
                bot.send_message(chat_id, "✅ Ответ отправлен.", reply_markup=main_keyboard(user_id))
                pending_action.pop(chat_id, None)
                return

            if action == "user_cancel_record":
                target = text
                uid_str = str(user_id)
                recs = data.get("records", {}).get(uid_str, [])
                removed = False
                for r in list(recs):
                    display = f"{r['spec']} {r['date']} {r['time']}"
                    if display == target:
                        data.setdefault("schedule", {}).setdefault(r['spec'], {}).setdefault(r['date'], []).append(r['time'])
                        recs.remove(r)
                        removed = True
                if removed:
                    data["records"][uid_str] = recs
                    save_data(data)
                    bot.send_message(chat_id, f"✔️ Запись отменена: {target}", reply_markup=main_keyboard(user_id))
                else:
                    bot.send_message(chat_id, "Не найдена запись с таким описанием.", reply_markup=main_keyboard(user_id))
                pending_action.pop(chat_id, None)
                return

        if text == "Запрос":
            pending_action[chat_id] = {"action": "user_request"}
            bot.send_message(chat_id, "Напишите ваш запрос (отправится админам):", reply_markup=remove_reply_kb())
            return
        if text == "Предложение":
            pending_action[chat_id] = {"action": "user_suggest"}
            bot.send_message(chat_id, "Напишите ваше предложение (отправится админам):", reply_markup=remove_reply_kb())
            return
        if text == "🔘 Начать":
            bot.send_message(chat_id, WELCOME_TEXT, reply_markup=main_keyboard(user_id))
            pending_action.pop(chat_id, None)
            return

        if text == "📋 Мои записи":
            uid_str = str(user_id)
            recs = data.get("records", {}).get(uid_str, [])
            if not recs:
                bot.send_message(chat_id, "У вас нет записей.", reply_markup=main_keyboard(user_id))
                return
            out = "🗓 Ваши записи:\n\n"
            kb = types.InlineKeyboardMarkup()
            for r in recs:
                out += f"👩‍⚕️ {r['spec']} — {r['date']} {r['time']}\n"
                try:
                    spec_idx = data["specialists"].index(r['spec'])
                except ValueError:
                    spec_idx = 0
                cb = f"cancel_my|{spec_idx}|{r['date']}|{r['time']}"
                kb.add(types.InlineKeyboardButton(f"Отменить: {r['spec']} {r['date']} {r['time']}", callback_data=cb))
            bot.send_message(chat_id, out, reply_markup=kb)
            return

        if user_id in ADMINS:
            if text == "⚙️ Админ панель":
                bot.send_message(chat_id, "⚙️ Админ-панель:", reply_markup=admin_keyboard())
                return
            if text == "🔙 На главную":
                bot.send_message(chat_id, "Главное меню:", reply_markup=main_keyboard(user_id))
                return
            if text == "📋 Все записи":
                show_all_records_admin(chat_id)
                return
            if text == "💬 Сообщения пользователей":
                show_messages_admin(chat_id)
                return
            if text == "⏰ Управление временем":
                data = load_data()
                kb = types.InlineKeyboardMarkup()
                for idx, spec in enumerate(data["specialists"]):
                    kb.add(types.InlineKeyboardButton(spec, callback_data=f"time_manage|{idx}"))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_menu_back"))
                bot.send_message(chat_id, "Выберите специалиста для управления временем:", reply_markup=kb)
                return
            if text == "👥 Управление специалистов":
                bot.send_message(chat_id, "Управление специалистами:", reply_markup=specialists_manage_keyboard())
                return
            if text == "Добавить специалиста":
                pending_action[chat_id] = {"action": "spec_add"}
                bot.send_message(chat_id, "Введите имя нового специалиста:", reply_markup=remove_reply_kb())
                return
            if text == "Удалить специалиста":
                pending_action[chat_id] = {"action": "spec_remove"}
                bot.send_message(chat_id, "Введите точное имя специалиста для удаления:", reply_markup=remove_reply_kb())
                return
            if text == "Переименовать специалиста":
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for spec in data["specialists"]:
                    kb.add(types.KeyboardButton(spec))
                kb.add("🔙 На главную")
                pending_action[chat_id] = {"action": "spec_rename", "old_name": None}
                bot.send_message(chat_id, "Выберите специалиста для переименования:", reply_markup=kb)
                return
            if pending_action.get(chat_id, {}).get("action") == "spec_rename" and text in data["specialists"]:
                pending_action[chat_id]["old_name"] = text
                bot.send_message(chat_id, f"Введите новое имя для {text}:", reply_markup=remove_reply_kb())
                return

        if text in data["specialists"]:
            idx = data["specialists"].index(text)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("📅 Записаться", callback_data=f"choose|{idx}"))
            kb.add(types.InlineKeyboardButton("💬 Написать специалисту", callback_data=f"msg_to_spec|{idx}"))
            kb.add(types.InlineKeyboardButton("❌ Отменить запись (мои записи)", callback_data=f"cancel_record|{idx}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
            bot.send_message(chat_id, f"Специалист: {text}", reply_markup=kb)
            return

        bot.send_message(chat_id, "Выберите действие из меню:", reply_markup=main_keyboard(user_id))

    except Exception:
        print("Error in all_text_handler:", traceback.format_exc())


@bot.callback_query_handler(func=lambda cb: True)
def inline_callbacks(cb):
    try:
        data = load_data()
        chat_id = cb.message.chat.id
        user_id = cb.from_user.id
        payload = cb.data

        if payload == "back_to_main":
            safe_edit_message(chat_id, cb.message.message_id, "Главное меню:", reply_markup=None)
            bot.send_message(chat_id, "Выберите действие:", reply_markup=main_keyboard(user_id))
            return

        if payload.startswith("msg_to_spec|"):
            _, spec_idx = payload.split("|", 1)
            spec = data["specialists"][int(spec_idx)]
            pending_action[chat_id] = {"action": "writing_message", "spec": spec}
            bot.send_message(chat_id, f"Напишите сообщение специалисту {spec}:", reply_markup=remove_reply_kb())
            return

        if payload.startswith("choose|"):
            _, spec_idx = payload.split("|", 1)
            spec = data["specialists"][int(spec_idx)]
            today = datetime.today()
            kb = types.InlineKeyboardMarkup(row_width=2)
            for i in range(7):
                d = today + timedelta(days=i)
                weekday = RU_WEEKDAYS[d.weekday()]
                label = f"{weekday}\n{d.day:02d}.{d.month:02d}"
                kb.add(types.InlineKeyboardButton(label, callback_data=f"date|{spec_idx}|{d.date().isoformat()}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
            safe_edit_message(chat_id, cb.message.message_id, f"Вы выбрали: {spec}\nВыберите дату:", reply_markup=kb)
            return

        if payload.startswith("date|"):
            _, spec_idx, date_iso = payload.split("|", 2)
            spec = data["specialists"][int(spec_idx)]
            slots = data.get("schedule", {}).get(spec, {}).get(date_iso, [])
            if not slots:
                safe_edit_message(chat_id, cb.message.message_id, "❌ Нет доступного времени для этой даты.")
                return
            kb = types.InlineKeyboardMarkup(row_width=3)
            for t in slots:
                kb.add(types.InlineKeyboardButton(t, callback_data=f"book|{spec_idx}|{date_iso}|{t}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"choose|{spec_idx}"))
            safe_edit_message(chat_id, cb.message.message_id, f"Выберите время для {spec} {date_iso}:", reply_markup=kb)
            return

        if payload.startswith("book|"):
            _, spec_idx, date_iso, t = payload.split("|", 3)
            spec = data["specialists"][int(spec_idx)]
            uid_str = str(user_id)
            username = get_username(cb.from_user)
            data.setdefault("schedule", {}).setdefault(spec, {}).setdefault(date_iso, [])
            data.setdefault("records", {}).setdefault(uid_str, [])
            if t not in data["schedule"][spec].get(date_iso, []):
                bot.answer_callback_query(cb.id, "Извините — этот слот уже занят или недоступен.")
                return
            rec = {"user_id": int(uid_str), "username": username, "spec": spec, "date": date_iso, "time": t, "ts": datetime.now().isoformat(), "notified": False}
            data["records"][uid_str].append(rec)
            data["schedule"][spec][date_iso].remove(t)
            save_data(data)
            safe_edit_message(chat_id, cb.message.message_id, f"✅ Вы записаны к {spec}\n📅 {date_iso}\n⏰ {t}")
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("📋 Посмотреть все записи", callback_data="admin_show_records"))
            for adm in ADMINS:
                try:
                    bot.send_message(adm, f"🆕 Новая запись!\n👤 {username}\n👩‍⚕️ {spec}\n📅 {date_iso}\n⏰ {t}", reply_markup=kb)
                except Exception:
                    print("notify admin failed", adm, traceback.format_exc())
            return

        if payload.startswith("cancel_record|"):
            uid_str = str(user_id)
            recs = data.get("records", {}).get(uid_str, [])
            if not recs:
                bot.answer_callback_query(cb.id, "У вас нет записей.")
                return
            out = "Выберите запись для отмены:\n\n"
            kb = types.InlineKeyboardMarkup()
            for r in recs:
                try:
                    spec_idx = data["specialists"].index(r['spec'])
                except ValueError:
                    spec_idx = 0
                cbdata = f"cancel_my|{spec_idx}|{r['date']}|{r['time']}"
                kb.add(types.InlineKeyboardButton(f"{r['spec']} {r['date']} {r['time']}", callback_data=cbdata))
            safe_edit_message(chat_id, cb.message.message_id, out, reply_markup=kb)
            return

        if payload.startswith("cancel_my|"):
            _, spec_idx, date_iso, t = payload.split("|", 3)
            spec = data["specialists"][int(spec_idx)]
            uid_str = str(user_id)
            recs = data.get("records", {}).get(uid_str, [])
            removed = False
            for r in list(recs):
                if r.get("spec") == spec and r.get("date") == date_iso and r.get("time") == t:
                    recs.remove(r)
                    data.setdefault("schedule", {}).setdefault(spec, {}).setdefault(date_iso, []).append(t)
                    removed = True
            if removed:
                if recs:
                    data["records"][uid_str] = recs
                else:
                    data["records"].pop(uid_str, None)
                save_data(data)
                safe_edit_message(chat_id, cb.message.message_id, f"✅ Запись отменена: {spec} {date_iso} {t}", reply_markup=None)
                bot.send_message(chat_id, "Запись успешно отменена.", reply_markup=main_keyboard(user_id))
            else:
                bot.answer_callback_query(cb.id, "Не удалось найти запись для отмены.")
            return

        if payload.startswith("time_manage|") and user_id in ADMINS:
            _, spec_idx = payload.split("|", 1)
            spec = data["specialists"][int(spec_idx)]
            today = datetime.today()
            kb = types.InlineKeyboardMarkup(row_width=2)
            for i in range(14):
                d = today + timedelta(days=i)
                kb.add(types.InlineKeyboardButton(f"{RU_WEEKDAYS[d.weekday()]} {d.day:02d}.{d.month:02d}", callback_data=f"time_date|{spec_idx}|{d.date().isoformat()}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_menu_back"))
            safe_edit_message(chat_id, cb.message.message_id, f"Управление временем для: {spec}", reply_markup=kb)
            return

        if payload.startswith("time_date|") and user_id in ADMINS:
            _, spec_idx, date_iso = payload.split("|", 2)
            spec = data["specialists"][int(spec_idx)]
            slots = data.setdefault("schedule", {}).setdefault(spec, {}).setdefault(date_iso, [])
            kb = types.InlineKeyboardMarkup(row_width=4)
            for t in PRESET_TIMES:
                status = "✅" if t in slots else "❌"
                kb.add(types.InlineKeyboardButton(f"{t} {status}", callback_data=f"time_toggle|{spec_idx}|{date_iso}|{t}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"time_manage|{spec_idx}"))
            kb.add(types.InlineKeyboardButton("🔙 На админку", callback_data="admin_menu_back"))
            safe_edit_message(chat_id, cb.message.message_id, f"Редактирование времени для {spec}\nДата: {date_iso}", reply_markup=kb)
            return

        if payload.startswith("time_toggle|") and user_id in ADMINS:
            _, spec_idx, date_iso, t = payload.split("|", 3)
            spec = data["specialists"][int(spec_idx)]
            slots = data.setdefault("schedule", {}).setdefault(spec, {}).setdefault(date_iso, [])
            if t in slots:
                slots.remove(t)
            else:
                slots.append(t)
            slots.sort()
            save_data(data)
            kb = types.InlineKeyboardMarkup(row_width=4)
            for ts in PRESET_TIMES:
                status = "✅" if ts in slots else "❌"
                kb.add(types.InlineKeyboardButton(f"{ts} {status}", callback_data=f"time_toggle|{spec_idx}|{date_iso}|{ts}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"time_date|{spec_idx}|{date_iso}"))
            kb.add(types.InlineKeyboardButton("🔙 На админку", callback_data="admin_menu_back"))
            safe_edit_message(chat_id, cb.message.message_id, f"Редактирование времени для {spec}\nДата: {date_iso}", reply_markup=kb)
            return

        if payload == "admin_menu_back" and user_id in ADMINS:
            bot.send_message(chat_id, "⚙️ Админ-панель:", reply_markup=admin_keyboard())
            return

        if payload == "admin_show_records" and user_id in ADMINS:
            show_all_records_admin(chat_id, edit_message=True, message_id=cb.message.message_id)
            return

        if payload == "admin_view_messages" and user_id in ADMINS:
            show_messages_admin(chat_id, edit_message=False)
            return

        if payload == "del_notify" and user_id in ADMINS:
            try:
                data.get("admin_notifications", {}).pop(str(user_id), None)
                save_data(data)
                try:
                    bot.delete_message(chat_id, cb.message.message_id)
                except Exception:
                    safe_edit_message(chat_id, cb.message.message_id, "Уведомление удалено.")
            except Exception:
                print("del_notify failed", traceback.format_exc())
            return

        if payload.startswith("reply|") and user_id in ADMINS:
            try:
                _, mid_s = payload.split("|", 1)
                mid = int(mid_s)
                msgs = data.get("messages", [])
                target = next((m for m in msgs if int(m.get("id", -1)) == mid), None)
                if not target:
                    bot.answer_callback_query(cb.id, "Сообщение не найдено.")
                    return
                pending_action[chat_id] = {"action": "admin_reply", "reply_mid": mid, "target_user_id": target.get("from_id")}
                bot.send_message(chat_id, f"Напишите ответ пользователю {target.get('from_username')}:", reply_markup=remove_reply_kb())
            except Exception:
                print("reply callback failed", traceback.format_exc())
            return

        if payload.startswith("delmsg|") and user_id in ADMINS:
            _, target = payload.split("|", 1)
            msgs = data.get("messages", [])
            if target == "all":
                data["messages"] = []
                save_data(data)
                safe_edit_message(chat_id, cb.message.message_id, "✅ Все сообщения удалены.")
                try:
                    increment_admin_notifications_for_all(data)
                except Exception:
                    print("failed to update admin notifications after del all", traceback.format_exc())
                return
            else:
                try:
                    mid = int(target)
                    new_msgs = [m for m in msgs if m.get("id") != mid]
                    data["messages"] = new_msgs
                    save_data(data)
                    safe_edit_message(chat_id, cb.message.message_id, f"✅ Сообщение {mid} удалено.")
                    try:
                        increment_admin_notifications_for_all(data)
                    except Exception:
                        print("failed to update admin notifications after del one", traceback.format_exc())
                except Exception:
                    safe_edit_message(chat_id, cb.message.message_id, "Ошибка удаления сообщения.")
                return

    except Exception:
        print("Error in inline_callbacks:", traceback.format_exc())

def send_my_records(chat_id, user_id):
    data = load_data()
    recs = data.get("records", {}).get(str(user_id), [])
    if not recs:
        bot.send_message(chat_id, "У вас нет записей.", reply_markup=main_keyboard(user_id))
        return
    out = "🗓 Ваши записи:\n\n"
    kb = types.InlineKeyboardMarkup()
    for r in recs:
        out += f"👩‍⚕️ {r['spec']} — {r['date']} {r['time']}\n"
        try:
            spec_idx = data["specialists"].index(r['spec'])
        except ValueError:
            spec_idx = 0
        kb.add(types.InlineKeyboardButton(f"Отменить: {r['spec']} {r['date']} {r['time']}", callback_data=f"cancel_my|{spec_idx}|{r['date']}|{r['time']}"))
    bot.send_message(chat_id, out, reply_markup=kb)

def show_all_records_admin(chat_id, edit_message=False, message_id=None):
    data = load_data()
    out = ""
    for uid, recs in data.get("records", {}).items():
        for r in recs:
            out += f"👤 {r['username']} | {r['spec']} | {r['date']} {r['time']}\n"
    if not out:
        out = "Записей нет."
    if edit_message:
        safe_edit_message(chat_id, message_id, out)
    else:
        bot.send_message(chat_id, out)

def show_messages_admin(chat_id, edit_message=False, message_id=None):
    try:
        data = load_data()
        msgs = data.get("messages", [])
        if not msgs:
            if edit_message:
                safe_edit_message(chat_id, message_id, "Сообщений нет.")
            else:
                bot.send_message(chat_id, "Сообщений нет.")
            return

        changed = False
        for m in msgs:
            if "id" not in m:
                m["id"] = data.get("next_message_id", 1)
                data["next_message_id"] = m["id"] + 1
                changed = True
            if "from_username" not in m:
                m["from_username"] = m.get("from_username") or m.get("username") or f"id{m.get('from_id','?')}"
                changed = True
            if "tag" not in m:
                if "spec" in m:
                    m["tag"] = "сообщение_специалисту"
                    changed = True
                else:
                    m["tag"] = m.get("tag", "")
        if changed:
            save_data(data)

        out_lines = []
        kb = types.InlineKeyboardMarkup()
        for m in msgs:
            mid = m.get("id")
            tag = m.get("tag", "")
            from_username = m.get("from_username", f"id{m.get('from_id','?')}")
            text = m.get("text", "")
            out_lines.append(f"📨 ID {mid} | {tag} | {from_username}\n{text}")
            btn_reply = types.InlineKeyboardButton(f"Ответить #{mid}", callback_data=f"reply|{mid}")
            btn_del = types.InlineKeyboardButton(f"Удалить #{mid}", callback_data=f"delmsg|{mid}")
            kb.add(btn_reply, btn_del)

        kb.add(types.InlineKeyboardButton("Удалить все сообщения", callback_data="delmsg|all"))
        out = "\n\n".join(out_lines)
        if edit_message:
            safe_edit_message(chat_id, message_id, out, reply_markup=kb)
        else:
            bot.send_message(chat_id, out, reply_markup=kb)
    except Exception:
        print("show_messages_admin error:", traceback.format_exc())
        try:
            if edit_message:
                safe_edit_message(chat_id, message_id, "Ошибка при получении сообщений.")
            else:
                bot.send_message(chat_id, "Ошибка при получении сообщений.")
        except Exception:
            print("failed to notify admin about show_messages_admin error")

def show_edit_specialists(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Добавить специалиста", "Удалить специалиста", "Переименовать специалиста")
    kb.add("🔙 На главную")
    bot.send_message(chat_id, "Управление специалистами:", reply_markup=kb)

def reminders_loop():
    while True:
        try:
            now = datetime.now()
            data = load_data()
            for uid_str, recs in data.get("records", {}).items():
                for r in recs:
                    try:
                        dt = datetime.fromisoformat(r["date"] + "T" + r["time"])
                    except Exception:
                        continue
                    seconds_left = (dt - now).total_seconds()
                    if 0 <= seconds_left <= 3600 and not r.get("notified", False):
                        try:
                            bot.send_message(int(uid_str), f"⏰ Напоминание: через {int(seconds_left//60)} минут — запись к {r['spec']} в {r['time']}")
                        except Exception:
                            pass
                        r["notified"] = True
            save_data(data)
        except Exception:
            print("reminders loop error:", traceback.format_exc())
        time.sleep(60)

threading.Thread(target=reminders_loop, daemon=True).start()

print("Бот запущен...")
bot.infinity_polling()
