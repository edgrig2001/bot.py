import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

# Telegram токен
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    print("Ошибка: TELEGRAM_TOKEN не задан")
    exit(1)

# SQLite база
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
    amount REAL,
    commission REAL,
    paid INTEGER
)
""")
conn.commit()

# состояние пользователя при добавлении объявления
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

# старт
async def start(update: Update, context: Update):
    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=main_keyboard()
    )

# обработка кнопок
async def button(update: Update, context: Update):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    data = query.data

    if data == "add":
        keyboard = [
            [InlineKeyboardButton("Работодатель", callback_data="role_employer")],
            [InlineKeyboardButton("Соискатель", callback_data="role_worker")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ]
        await query.edit_message_text("Выберите роль:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("role_"):
        role = "работодатель" if data=="role_employer" else "соискатель"
        user_state[chat_id] = {"role": role}
        await query.edit_message_text("Теперь добавим название объявления:", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести название", callback_data="enter_title")]]))

    elif data == "enter_title":
        user_state[chat_id]["step"] = "title"
        await query.edit_message_text("Напиши название в чат:")

    elif data == "enter_desc":
        user_state[chat_id]["step"] = "desc"
        await query.edit_message_text("Напиши описание в чат:")

    elif data == "enter_amount":
        user_state[chat_id]["step"] = "amount"
        await query.edit_message_text("Напиши сумму (число) в ₽:")

    elif data == "confirm":
        state = user_state.get(chat_id, {})
        if not state:
            await query.edit_message_text("Ошибка, состояние не найдено.", reply_markup=main_keyboard())
            return
        cursor.execute(
            "INSERT INTO jobs (user_id, role, city, title, description, amount, commission, paid) VALUES (?,?,?,?,?,?,?,?)",
            (chat_id, state["role"], "Челны", state["title"], state["desc"], state["amount"], state["commission"], 1)
        )
        conn.commit()
        user_state.pop(chat_id)
        await query.edit_message_text("Объявление опубликовано!", reply_markup=main_keyboard())

    elif data == "search":
        jobs = cursor.execute("SELECT title, description, amount, commission, city FROM jobs WHERE paid=1").fetchall()
        if not jobs:
            text = "Пока нет оплаченных объявлений."
        else:
            text = "\n\n".join([f"{t[0]} ({t[4]})\n{t[1]}\nСумма: {t[2]} ₽, Комиссия: {t[3]} ₽" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif data == "my":
        jobs = cursor.execute("SELECT title, description, amount, commission, paid FROM jobs WHERE user_id=?", (chat_id,)).fetchall()
        if not jobs:
            text = "У тебя нет объявлений."
        else:
            text = "\n\n".join([f"{t[0]}\n{t[1]}\nСумма: {t[2]} ₽\nКомиссия: {t[3]} ₽\nОплачено: {'Да' if t[4] else 'Нет'}" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif data == "help":
        await query.edit_message_text(
            "Добавление через кнопки:\n1) Выбираешь роль\n2) Ввод названия, описания и суммы\n3) Оплата кнопкой\n\n"
            "Искать объявления — кнопка 'Искать работу/услугу'\nМои объявления — кнопка 'Мои объявления'",
            reply_markup=main_keyboard()
        )

    elif data == "cancel":
        user_state.pop(chat_id, None)
        await query.edit_message_text("Действие отменено.", reply_markup=main_keyboard())

# обработка сообщений для ввода текста
async def handle_message(update: Update, context: Update):
    chat_id = update.message.chat.id
    state = user_state.get(chat_id, {})
    step = state.get("step")
    if not step:
        return

    text = update.message.text.strip()
    if step == "title":
        state["title"] = text
        await update.message.reply_text("Название сохранено.\nНажми кнопку 'Ввести описание'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести описание", callback_data="enter_desc")]]))
    elif step == "desc":
        state["desc"] = text
        await update.message.reply_text("Описание сохранено.\nНажми кнопку 'Ввести сумму'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести сумму", callback_data="enter_amount")]]))
    elif step == "amount":
        try:
            amount = float(text)
            state["amount"] = amount
            state["commission"] = round(amount * 0.08, 2)
            total = round(amount + state["commission"], 2)
            await update.message.reply_text(f"Ваша сумма: {amount} ₽\nКомиссия 8%: {state['commission']} ₽\nИтого к оплате: {total} ₽",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить", callback_data="confirm"), InlineKeyboardButton("Отмена", callback_data="cancel")]]))
            state.pop("step")
        except:
            await update.message.reply_text("Введите корректное число для суммы!")

# запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Бот запускается через polling...")
    app.run_polling()
