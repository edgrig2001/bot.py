import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import openai

# Токены берём из Environment
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# Память истории диалога
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
        "Привет! Я бот с AI. Нажми кнопку или напиши сообщение.",
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

# Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append({"role": "user", "content": user_text})

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=chat_history[chat_id]
        )
        answer = response.choices[0].message.content.strip()
        chat_history[chat_id].append({"role": "assistant", "content": answer})
        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка AI: {e}", reply_markup=main_keyboard())

# Запуск через Webhook для Render
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8443))
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # Настройка webhook
    WEBHOOK_URL = f"https://<твое-service-name>.onrender.com/{TELEGRAM_TOKEN}"
    app.bot.set_webhook(WEBHOOK_URL)
    print(f"Бот запускается на webhook {WEBHOOK_URL} ...")

    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TELEGRAM_TOKEN)
