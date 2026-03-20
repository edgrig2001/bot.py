import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import openai

# Берём токены из Environment
TELEGRAM_TOKEN = os.environ["8585362055:AAEjQwzD42lqksiU6qtvO7vDh9q6nNl8nzo"]
OPENAI_API_KEY = os.environ["sk-1234567890abcdef1234567890abcdef12345678"]

openai.api_key = OPENAI_API_KEY

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

# Обработчик команд /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_history[chat_id] = []
    await update.message.reply_text("Привет! Я бот с AI. Нажми кнопку или напиши сообщение.", reply_markup=main_keyboard())

# Обработчик кнопок
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

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in chat_history:
        chat_history[chat_id] = []

    # Добавляем сообщение пользователя в историю
    chat_history[chat_id].append({"role": "user", "content": user_text})

    # Запрос к OpenAI
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=chat_history[chat_id]
        )
        answer = response.choices[0].message.content.strip()
        # Добавляем ответ AI в историю
        chat_history[chat_id].append({"role": "assistant", "content": answer})
        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка AI: {e}", reply_markup=main_keyboard())

# Основная функция запуска
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Бот запускается...")
    app.run_polling()