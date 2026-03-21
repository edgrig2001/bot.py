import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Telegram token
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

if not TELEGRAM_TOKEN:
    print("Ошибка: TELEGRAM_TOKEN не задан")
    exit(1)

# SQLite для объявлений
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
    paid INTEGER
)
""")
conn.commit()

# Состояние для добавления объявления
user_state = {}

# Главное меню
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("Добавить объявление", callback_data="add")],
        [InlineKeyboardButton("Искать работу/услугу", callback_data="search")],
        [InlineKeyboardButton("Мои объявления", callback_data="my")],
        [InlineKeyboardButton("Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=main_keyboard()
    )

# Обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    data = query.data

    # Главное меню
    if data == "add":
        keyboard = [
            [InlineKeyboardButton("Работодатель", callback_data="role_employer")],
            [InlineKeyboardButton("Соискатель", callback_data="role_worker")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ]
        await query.edit_message_text("Выбери роль:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("role_"):
        role = "работодатель" if data=="role_employer" else "соискатель"
        user_state[chat_id] = {"role": role}
        await query.edit_message_text(f"Вы выбрали: {role}\nТеперь нажмите кнопку 'Ввести название'", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести название", callback_data="enter_title")]]))
    elif data == "enter_title":
        user_state[chat_id]["step"] = "title"
        await query.edit_message_text("Напиши название объявления в чат:")
    elif data == "enter_desc":
        user_state[chat_id]["step"] = "desc"
        await query.edit_message_text("Напиши описание объявления в чат:")
    elif data == "enter_price":
        user_state[chat_id]["step"] = "price"
        await query.edit_message_text("Напиши сумму (в ₽) в чат:")
    elif data == "confirm":
        state = user_state.get(chat_id, {})
        cursor.execute("INSERT INTO jobs (user_id, role, city, title, description, price, paid) VALUES (?,?,?,?,?,?,?)",
                       (chat_id, state["role"], "Челны", state["title"], state["desc"], state["price"], 1))
        conn.commit()
        user_state.pop(chat_id)
        await query.edit_message_text("Объявление опубликовано!", reply_markup=main_keyboard())
    elif data == "search":
        jobs = cursor.execute("SELECT title, description, price, city FROM jobs WHERE paid=1").fetchall()
        if not jobs:
            text = "Пока нет оплаченных объявлений."
        else:
            text = "\n\n".join([f"{t[0]} ({t[3]})\n{t[1]}\nКомиссия: {t[2]} ₽" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())
    elif data == "my":
        jobs = cursor.execute("SELECT title, description, price, paid FROM jobs WHERE user_id=?", (chat_id,)).fetchall()
        if not jobs:
            text = "У тебя нет объявлений."
        else:
            text = "\n\n".join([f"{t[0]}\n{t[1]}\nКомиссия: {t[2]} ₽\nОплачено: {'Да' if t[3] else 'Нет'}" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())
    elif data == "help":
        await query.edit_message_text("Добавление через кнопки.\nОплата имитация через кнопку.\nПоиск — кнопка 'Искать работу/услугу'.", reply_markup=main_keyboard())
    elif data == "cancel":
        user_state.pop(chat_id, None)
        await query.edit_message_text("Действие отменено.", reply_markup=main_keyboard())

# Обработка сообщений для ввода текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    state = user_state.get(chat_id, {})
    step = state.get("step")
    if not step:
        return
    if step == "title":
        state["title"] = update.message.text
        await update.message.reply_text("Название сохранено.\nНажми кнопку 'Ввести описание'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести описание", callback_data="enter_desc")]]))
    elif step == "desc":
        state["desc"] = update.message.text
        await update.message.reply_text("Описание сохранено.\nНажми кнопку 'Ввести комиссию'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести комиссию", callback_data="enter_price")]]))
    elif step == "price":
        try:
            state["price"] = float(update.message.text)
        except:
            await update.message.reply_text("Введи число для комиссии")
            return
        await update.message.reply_text(f"Сумма комиссии: {state['price']} ₽\nПодтвердить публикацию?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Подтвердить", callback_data="confirm"), InlineKeyboardButton("Отмена", callback_data="cancel")]]))
        state.pop("step")

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Бот запускается через polling...")
    app.run_polling()
