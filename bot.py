import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Токен бота
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# Словарь для хранения истории диалога
chat_history = {}

# Кнопки
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
        "Привет! Я бот с AI (Hugging Face). Нажми кнопку или напиши сообщение.",
        reply_markup=main_keyboard()
    )

# Кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()
    if query.data == "start":
        chat_history[chat_id] = []
        await query.edit_message_text("Начинаем заново! Отправь сообщение.", reply_markup=main_keyboard())
    elif query.data == "help":
        await query.edit_message_text(
            "Я могу отвечать на твои сообщения с помощью AI.\n"
            "Кнопки:\n/start — начать заново\n/help — помощь\n/clear — очистить историю",
            reply_markup=main_keyboard()
        )
    elif query.data == "clear":
        chat_history[chat_id] = []
        await query.edit_message_text("История очищена.", reply_markup=main_keyboard())

# Функция запроса к бесплатной модели Hugging Face
def query_huggingface(prompt):
    # Используем модель GPT-J бесплатно через Inference API Hugging Face
    url = "https://api-inference.huggingface.co/models/EleutherAI/gpt-j-6B"
    headers = {"Authorization": f"Bearer {os.environ.get('HF_API_KEY','')}"}
    payload = {"inputs": prompt}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code == 200:
        try:
            return response.json()[0]['generated_text']
        except Exception:
            return "AI не смог сгенерировать ответ."
    else:
        return f"Ошибка AI: {response.status_code}"

# Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append(f"User: {user_text}")

    # Формируем историю в один текст
    prompt = "\n".join(chat_history[chat_id]) + "\nAI:"

    answer = query_huggingface(prompt).strip()
    chat_history[chat_id].append(f"AI: {answer}")

    await update.message.reply_text(answer, reply_markup=main_keyboard())

# Запуск через polling
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Бот запускается через polling...")
    app.run_polling()
