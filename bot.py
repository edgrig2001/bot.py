import os
import sqlite3
import threading
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# ---------------- НАСТРОЙКИ ----------------
ADMIN_ID = 869818784
DONATE_URL = "https://вразработке"

# ---------------- Flask ----------------
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

# ---------------- TOKEN ----------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

if not TELEGRAM_TOKEN:
    print("Нет токена")
    exit(1)

# ---------------- БАЗА ----------------
conn = sqlite3.connect("jobs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    city TEXT,
    title TEXT,
    description TEXT,
    price REAL,
    contact TEXT,
    paid INTEGER
)
""")
conn.commit()

user_state = {}

# ---------------- МЕНЮ ----------------
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Добавить объявление", callback_data="add")],
        [InlineKeyboardButton("Искать работу/услугу", callback_data="search")],
        [InlineKeyboardButton("Мои объявления", callback_data="my")],
        [InlineKeyboardButton("Чаевые 💸", url=DONATE_URL)],
        [InlineKeyboardButton("Помощь ℹ️", callback_data="help")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
    ])

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_state[chat_id] = {"step": "auth"}
    await update.message.reply_text("👤 Введите ваше имя:")

# ---------------- MENU ----------------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.message.chat.id, None)
    await update.message.reply_text("🏠 Главное меню:", reply_markup=main_keyboard())

# ---------------- КНОПКИ ----------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    data = query.data

    if data == "menu":
        user_state.pop(chat_id, None)
        await query.edit_message_text("🏠 Главное меню:", reply_markup=main_keyboard())

    elif data == "add":
        keyboard = [
            [InlineKeyboardButton("Работодатель", callback_data="role_employer")],
            [InlineKeyboardButton("Соискатель", callback_data="role_worker")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ]
        await query.edit_message_text("👔 Выберите роль:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("role_"):
        role = "работодатель" if data == "role_employer" else "соискатель"
        user_state[chat_id] = {"role": role}
        await query.edit_message_text(
            f"Вы выбрали: {role}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести название", callback_data="enter_title")]])
        )

    elif data == "enter_title":
        user_state[chat_id]["step"] = "title"
        await query.edit_message_text("📝 Введите название:")

    elif data == "enter_desc":
        user_state[chat_id]["step"] = "desc"
        await query.edit_message_text("📄 Введите описание:")

    elif data == "enter_price":
        user_state[chat_id]["step"] = "price"
        await query.edit_message_text("💰 Введите сумму:")

    elif data == "confirm":
        state = user_state.get(chat_id, {})

        cursor.execute(
            "INSERT INTO jobs (user_id, role, city, title, description, price, contact, paid) VALUES (?,?,?,?,?,?,?,?)",
            (chat_id, state["role"], "Челны", state["title"], state["desc"], state["price"], state["contact"], 1)
        )
        conn.commit()

        # 🔥 УВЕДОМЛЕНИЕ ТЕБЕ
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Новое объявление!\n\n"
            f"👤 {state.get('name','')}\n"
            f"📞 {state['contact']}\n"
            f"💼 {state['title']}\n"
            f"💰 {state['price']} ₽"
        )

        user_state.pop(chat_id)

        await query.edit_message_text("✅ Объявление опубликовано!", reply_markup=main_keyboard())

    elif data == "search":
        jobs = cursor.execute("SELECT title, description, price, city, contact FROM jobs WHERE paid=1").fetchall()
        text = "😔 Нет объявлений" if not jobs else "\n\n".join(
            [f"{t[0]} ({t[3]})\n{t[1]}\n💰 {t[2]} ₽\n📞 {t[4]}" for t in jobs]
        )
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif data == "my":
        jobs = cursor.execute("SELECT title, description, price, paid FROM jobs WHERE user_id=?", (chat_id,)).fetchall()
        text = "😔 Нет объявлений" if not jobs else "\n\n".join(
            [f"{t[0]}\n{t[1]}\n💰 {t[2]} ₽\nОплачено: {'Да' if t[3] else 'Нет'}" for t in jobs]
        )
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif data == "help":
        await query.edit_message_text(
            "✨ *Спасибо, что используете наш бот!*\n\n"
            "💼 Добавляйте объявления\n"
            "🔍 Находите клиентов\n\n"
            "💸 Поддержите проект через 'Чаевые'\n\n"
            "📩 @grigelav",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif data == "cancel":
        user_state.pop(chat_id, None)
        await query.edit_message_text("❌ Отменено", reply_markup=main_keyboard())

# ---------------- СООБЩЕНИЯ ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    state = user_state.get(chat_id, {})
    step = state.get("step")

    if not step:
        await update.message.reply_text("❗ Используйте кнопки ниже", reply_markup=main_keyboard())
        return

    if step == "auth":
        state["name"] = update.message.text
        state["step"] = None
        await update.message.reply_text("✅ Готово!", reply_markup=main_keyboard())
        return

    if step == "title":
        state["title"] = update.message.text
        await update.message.reply_text("Ок", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести описание", callback_data="enter_desc")]]))

    elif step == "desc":
        state["desc"] = update.message.text
        await update.message.reply_text("Ок", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести сумму", callback_data="enter_price")]]))

    elif step == "price":
        try:
            state["price"] = float(update.message.text)
        except:
            await update.message.reply_text("Введите число")
            return

        state["step"] = "contact"
        await update.message.reply_text("📞 Введите ник или номер:")

    elif step == "contact":
        state["contact"] = update.message.text
        await update.message.reply_text(
            f"💰 {state['price']} ₽\n📞 {state['contact']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Подтвердить", callback_data="confirm"),
                 InlineKeyboardButton("Отмена", callback_data="cancel")]
            ])
        )
        state.pop("step")

# ---------------- ЗАПУСК ----------------
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.bot.delete_webhook(drop_pending_updates=True)

    print("BOT STARTED")
    app.run_polling()

    app.bot.delete_webhook(drop_pending_updates=True)

    print("BOT STARTED")
    app.run_polling()
