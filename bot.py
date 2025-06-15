import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import Updater, CommandHandler

# Увімкнути логування
logging.basicConfig(level=logging.INFO)

# Отримуємо JSON з ключами з середовища
# ⚠️ У Render додай змінну CREDS_JSON (дивись далі)
creds_dict = json.loads(os.environ["CREDS_JSON"])

# Права доступу до Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ⚠️ Заміни назву таблиці на свою (наприклад, "Volleyball Scores")
sheet = client.open("Volleyball Scores").sheet1

# Функція /result команда1 рахунок1 команда2 рахунок2
def result(update, context):
    try:
        args = context.args
        if len(args) != 4:
            raise ValueError("Неправильна кількість аргументів")

        team1 = args[0]
        score1 = int(args[1])
        team2 = args[2]
        score2 = int(args[3])

        # Запис у таблицю
        sheet.append_row([team1, score1, team2, score2])
        update.message.reply_text(f"✅ Збережено результат: {team1} {score1} — {team2} {score2}")

    except Exception as e:
        logging.error(e)
        update.message.reply_text("❌ Формат команди: /result команда1 рахунок1 команда2 рахунок2")

def main():
    # ⚠️ У Render додай змінну BOT_TOKEN (з BotFather)
    bot_token = os.environ["BOT_TOKEN"]

    updater = Updater(bot_token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("result", result))

    logging.info("🤖 Бот запущений і слухає команди.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
