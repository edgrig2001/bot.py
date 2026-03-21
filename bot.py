import os
import asyncio
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# ---------------- БАЗА ----------------
conn = sqlite3.connect("jobs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    title TEXT,
    description TEXT,
    amount REAL,
    commission REAL,
    name TEXT
)
""")
conn.commit()

user_state = {}

# ---------------- HTTP ДЛЯ RENDER ----------------
def start_http():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print("PORT OPEN", PORT)
    server.serve_forever()

# ---------------- КНОПКИ ----------------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Добавить объявление", callback_data="add")],
        [InlineKeyboardButton("Смотреть объявления", callback_data="list")]
    ])

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=main_menu())

# ---------------- КНОПКИ ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "add":
        user_state[uid] = {}
        await q.edit_message_text(
            "Кто вы:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Работодатель", callback_data="emp")],
                [InlineKeyboardButton("Соискатель", callback_data="wrk")]
            ])
        )

    elif data in ["emp", "wrk"]:
        user_state[uid]["role"] = "работодатель" if data == "emp" else "соискатель"
        user_state[uid]["step"] = "title"
        await q.edit_message_text("Введите название:")

    elif data == "list":
        rows = cursor.execute("SELECT title, description, amount, commission, name FROM jobs").fetchall()
        if not rows:
            text = "Нет объявлений"
        else:
            text = "\n\n".join([
                f"{r[0]}\n{r[1]}\nСумма: {r[2]} ₽\nКомиссия: {r[3]} ₽\nИмя: {r[4]}"
                for r in rows
            ])
        await q.edit_message_text(text, reply_markup=main_menu())

# ---------------- ТЕКСТ ----------------
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat.id

    if uid not in user_state:
        return

    state = user_state[uid]
    step = state.get("step")
    text = update.message.text.strip()

    if step == "title":
        state["title"] = text
        state["step"] = "desc"
        await update.message.reply_text("Введите описание:")

    elif step == "desc":
        state["description"] = text
        state["step"] = "amount"
        await update.message.reply_text("Введите сумму:")

    elif step == "amount":
        try:
            amount = float(text)
            state["amount"] = amount
            state["commission"] = round(amount * 0.08, 2)
            state["step"] = "name"

            await update.message.reply_text(
                f"Комиссия 8%: {state['commission']} ₽\nВведите имя:"
            )
        except:
            await update.message.reply_text("Введите число")

    elif step == "name":
        state["name"] = text

        cursor.execute(
            "INSERT INTO jobs (user_id, role, title, description, amount, commission, name) VALUES (?,?,?,?,?,?,?)",
            (
                uid,
                state["role"],
                state["title"],
                state["description"],
                state["amount"],
                state["commission"],
                state["name"],
            )
        )
        conn.commit()

        user_state.pop(uid)

        await update.message.reply_text("Объявление добавлено ✅", reply_markup=main_menu())

# ---------------- ЗАПУСК ----------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    await app.bot.delete_webhook(drop_pending_updates=True)

    print("BOT STARTED")

    await app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    asyncio.run(main())
