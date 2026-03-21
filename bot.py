import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# Токен Telegram бота
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# Создаём базу данных SQLite для хранения объявлений
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

# Состояния для ConversationHandler
ROLE, TITLE, DESC, PRICE, CONFIRM = range(5)

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
        "Привет! Я бот для поиска работы и услуг.\nВыбери действие:",
        reply_markup=main_keyboard()
    )

# Обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add":
        await query.edit_message_text("Ты работодатель или соискатель? Напиши 'работодатель' или 'соискатель'")
        return ROLE
    elif query.data == "search":
        jobs = cursor.execute("SELECT title, description, price, city FROM jobs WHERE paid=1").fetchall()
        if not jobs:
            text = "Пока нет оплаченных объявлений."
        else:
            text = "\n\n".join([f"{t[0]} ({t[3]})\n{t[1]}\nКомиссия: {t[2]} ₽" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())
        return ConversationHandler.END
    elif query.data == "my":
        chat_id = query.from_user.id
        jobs = cursor.execute("SELECT title, description, price, paid FROM jobs WHERE user_id=?", (chat_id,)).fetchall()
        if not jobs:
            text = "У тебя нет объявлений."
        else:
            text = "\n\n".join([f"{t[0]}\n{t[1]}\nКомиссия: {t[2]} ₽\nОплачено: {'Да' if t[3] else 'Нет'}" for t in jobs])
        await query.edit_message_text(text, reply_markup=main_keyboard())
        return ConversationHandler.END
    elif query.data == "help":
        await query.edit_message_text(
            "Добавление объявлений: нужно указать роль, название, описание и сумму комиссии.\n"
            "Оплата комиссии пока имитируется кнопкой.\n"
            "Искать работу/услугу: просматриваются только оплаченные объявления.",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END

# Добавление объявления — шаги
async def role_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text not in ["работодатель", "соискатель"]:
        await update.message.reply_text("Пиши только 'работодатель' или 'соискатель'")
        return ROLE
    context.user_data["role"] = text
    await update.message.reply_text("Введи название объявления:")
    return TITLE

async def title_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("Введи описание:")
    return DESC

async def desc_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = update.message.text
    await update.message.reply_text("Введи сумму комиссии (в ₽):")
    return PRICE

async def price_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data["price"] = price
    except:
        await update.message.reply_text("Введи число для комиссии")
        return PRICE
    await update.message.reply_text(f"Твоя комиссия: {price} ₽\nНажми 'Оплатить' чтобы опубликовать или /cancel для отмены",
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить", callback_data="pay")]]))
    return CONFIRM

async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    # Сохраняем объявление как оплачено (имитация платежа)
    cursor.execute(
        "INSERT INTO jobs (user_id, role, city, title, description, price, paid) VALUES (?,?,?,?,?,?,?)",
        (chat_id, context.user_data["role"], "Челны", context.user_data["title"], context.user_data["desc"], context.user_data["price"], 1)
    )
    conn.commit()
    await query.edit_message_text("Объявление опубликовано!", reply_markup=main_keyboard())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено", reply_markup=main_keyboard())
    return ConversationHandler.END

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Основные кнопки
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Conversation для добавления объявления
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & (~filters.COMMAND), role_step)],
        states={
            ROLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), role_step)],
            TITLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), title_step)],
            DESC: [MessageHandler(filters.TEXT & (~filters.COMMAND), desc_step)],
            PRICE: [MessageHandler(filters.TEXT & (~filters.COMMAND), price_step)],
            CONFIRM: [CallbackQueryHandler(confirm_step, pattern="pay")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    print("Бот для поиска работы/услуг запускается...")
    app.run_polling()
