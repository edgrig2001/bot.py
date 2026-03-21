import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Токен Telegram бота (берется из Environment)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# История диалога по chat_id
chat_history = {}

# Основные кнопки
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("Старт", callback_data="start")],
        [InlineKeyboardButton("Помощь", callback_data="help")],
        [InlineKeyboardButton("Очистить историю", callback_data="clear")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_history[chat_id] = []
    await update.message.reply_text(
        "Привет! Я бот с AI на бесплатной модели Hugging Face.\nНапиши сообщение или используй кнопки ниже.",
        reply_markup=main_keyboard()
    )

# Обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()
    if query.data == "start":
        chat_history[chat_id] = []
        await query.edit_message_text("Начинаем новый диалог. Напиши сообщение!", reply_markup=main_keyboard())
    elif query.data == "help":
        await query.edit_message_text(
            "Я отвечаю на твои сообщения с помощью бесплатного AI.\n\n"
            "Кнопки:\n"
            "/start — начать заново\n"
            "/help — помощь\n"
            "/clear — очистить историю",
            reply_markup=main_keyboard()
        )
    elif query.data == "clear":
        chat_history[chat_id] = []
        await query.edit_message_text("История очищена.", reply_markup=main_keyboard())

# Функция запроса к бесплатной модели Hugging Face
def query_huggingface(prompt):
    """
    Используем бесплатную модель GPT-J через Hugging Face Inference API.
    Для бесплатного использования HF_API_KEY можно не указывать.
    """
    url = "https://api-inference.huggingface.co/models/EleutherAI/gpt-j-6B"
    headers = {}
    hf_key = os.environ.get("HF_API_KEY", "")
    if hf_key:
        headers["Authorization"] = f"Bearer {hf_key}"

    try:
        response = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result[0].get('generated_text', "AI не смог сгенерировать ответ.")
        else:
            return f"Ошибка AI: {response.status_code}"
    except Exception as e:
        return f"Ошибка AI: {e}"

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append(f"User: {user_text}")
    prompt = "\n".join(chat_history[chat_id]) + "\nAI:"

    answer = query_huggingface(prompt).strip()
    chat_history[chat_id].append(f"AI: {answer}")

    await update.message.reply_text(answer, reply_markup=main_keyboard())

# Основной запуск через polling
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Бот запускается через polling... Бот будет работать 24/7 на Render.")
    app.run_polling()
