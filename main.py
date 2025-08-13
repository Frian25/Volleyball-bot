import logging
import time
import os
import atexit
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CallbackContext, JobQueue, CommandHandler, CallbackQueryHandler, PollHandler, PollAnswerHandler
from queue import Queue

from config import BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL
from handlers.generate_teams import generate_teams
from handlers.result import result
from handlers.delete import delete
from handlers.stats import stats
from handlers.leaderboard import leaderboard
from handlers.help_command import help_command
from handlers.button_handler import button_handler
from handlers.appeal import appeal, check_polls_manual
from handlers.poll_handler import poll_handler, poll_answer_handler

# 🔧 Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 🧠 Telegram Bot
bot = Bot(token=BOT_TOKEN)

# 🌐 Flask додаток
app = Flask(__name__)

# 📬 Dispatcher + JobQueue
update_queue = Queue()
job_queue = JobQueue()
dispatcher = Dispatcher(bot, update_queue, use_context=True, job_queue=job_queue)
job_queue.set_dispatcher(dispatcher)

# 📌 Реєстрація хендлерів
dispatcher.add_handler(CommandHandler("generate_teams", generate_teams))
dispatcher.add_handler(CommandHandler("result", result))
dispatcher.add_handler(CommandHandler("delete", delete))
dispatcher.add_handler(CommandHandler("stats", stats))
dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("start", help_command))
dispatcher.add_handler(CommandHandler("appeal", appeal))
dispatcher.add_handler(CommandHandler("check_polls", check_polls_manual))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(PollHandler(poll_handler))
dispatcher.add_handler(PollAnswerHandler(poll_answer_handler))

# Додайте цю функцію в main.py після імпортів

def periodic_poll_check(context: CallbackContext):
    """Періодично перевіряє та закриває прострочені polls"""
    try:
        from datetime import datetime
        from services.sheets import appeals_sheet
        from services.appeal_service import process_poll_results
        from handlers.appeal import send_poll_results, update_poll_status_in_sheet

        current_time = datetime.now()

        all_rows = appeals_sheet.get_all_values()
        if len(all_rows) <= 1:
            return

        headers = all_rows[0]
        col_idx = {header.strip().lower(): idx for idx, header in enumerate(headers)}

        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) < 8:
                continue

            try:
                status = row[col_idx.get('status', 6)].strip()
                if status != 'active':
                    continue

                end_time_str = row[col_idx.get('end_time', 7)].strip()
                poll_id = row[col_idx.get('poll_id', 3)].strip()
                chat_id = int(row[col_idx.get('chat_id', 5)])
                message_id = int(row[col_idx.get('message_id', 4)])
                team_name = row[col_idx.get('team_name', 2)].strip()

                try:
                    end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

                if current_time >= end_time:
                    print(f"🕐 Periodic check: closing expired poll {poll_id}")

                    try:
                        poll = context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
                        poll_results = {opt.text: opt.voter_count for opt in poll.options}
                        winner = process_poll_results(poll_id, poll_results)

                        update_poll_status_in_sheet(poll_id, 'completed')
                        send_poll_results(context, chat_id, team_name, poll_results, winner, poll.total_voter_count)

                        print(f"✅ Periodic check: successfully closed poll {poll_id}")

                    except Exception as poll_error:
                        if "Poll has already been closed" in str(poll_error):
                            update_poll_status_in_sheet(poll_id, 'completed')
                        else:
                            print(f"❌ Periodic check error for poll {poll_id}: {poll_error}")

            except Exception as row_error:
                print(f"⚠️ Periodic check: error processing row {i}: {row_error}")

    except Exception as e:
        print(f"❌ Error in periodic poll check: {e}")


# Додайте цей рядок після start_job_queue() у функції запуску:

# Запуск періодичної перевірки polls кожні 2 хвилини
job_queue.run_repeating(periodic_poll_check, interval=120, first=60)
print("✅ Periodic poll checker started (every 2 minutes)")

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

# 🔌 Webhook setup
def setup_webhook():
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"✅ Webhook set: {WEBHOOK_URL}")
    else:
        logging.warning("⚠️ WEBHOOK_URL is not set")

# 🏃‍♂️ Запуск JobQueue
def start_job_queue():
    try:
        job_queue.start()
        logging.info("✅ JobQueue started successfully")
    except Exception as e:
        logging.error(f"❌ Failed to start JobQueue: {e}")

# 🛑 Зупинка JobQueue при завершенні
def stop_job_queue():
    try:
        if job_queue:
            job_queue.stop()
            logging.info("✅ JobQueue stopped")
    except Exception as e:
        logging.error(f"❌ Error stopping JobQueue: {e}")

# Реєструємо функцію для зупинки при завершенні програми
atexit.register(stop_job_queue)

# ▶️ Запуск компонентів
setup_webhook()
start_job_queue()

# ▶️ Запуск Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))