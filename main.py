import logging
import time
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler

from config import BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL
from handlers.generate_teams import generate_teams
from handlers.result import result
from handlers.delete import delete
from handlers.stats import stats
from handlers.leaderboard import leaderboard
from handlers.help_command import help_command
from handlers.button_handler import button_handler

# 🔧 Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 🧠 Telegram Bot
bot = Bot(token=BOT_TOKEN)

# 🌐 Flask додаток
app = Flask(__name__)

# 🧵 Dispatcher (обробник команд)
dispatcher = Dispatcher(bot, None, workers=4)

# 📌 Реєстрація хендлерів
dispatcher.add_handler(CommandHandler("generate_teams", generate_teams))
dispatcher.add_handler(CommandHandler("result", result))
dispatcher.add_handler(CommandHandler("delete", delete))
dispatcher.add_handler(CommandHandler("stats", stats))
dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("start", help_command))
dispatcher.add_handler(CallbackQueryHandler(button_handler))

# 🚀 Webhook endpoint
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, bot)
    dispatcher.process_update(update)
    return "OK"

# 🔍 Health check
@app.route("/", methods=["GET"])
def root():
    return "✅ Volleyball Rating Bot is running!"

@app.route("/health", methods=["GET"])
def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

# 🔌 Webhook setup при запуску
def setup_webhook():
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"✅ Webhook set: {WEBHOOK_URL}")
    else:
        logging.warning("⚠️ WEBHOOK_URL is not set")

# ▶️ Запуск Flask
if __name__ == "__main__":
    setup_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
