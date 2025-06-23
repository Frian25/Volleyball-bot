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
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250").worksheet("Matches")
# Функція /result команда1 рахунок1 команда2 рахунок2
def result(update, context):
    try:
        # 1. Отримуємо повідомлення у форматі: "Команда1 2 - Команда2 1"
        text = " ".join(context.args)
        if "-" not in text:
            raise ValueError("Формат має бути: Команда1 2 - Команда2 1")

        part1, part2 = [part.strip() for part in text.split("-", 1)]

        tokens1 = part1.rsplit(" ", 1)
        tokens2 = part2.rsplit(" ", 1)

        if len(tokens1) != 2 or len(tokens2) != 2:
            raise ValueError("Не вдалося розпізнати команди або рахунки")

        team1 = tokens1[0]
        score1 = int(tokens1[1])
        team2 = tokens2[0]
        score2 = int(tokens2[1])

        # 2. Поточна дата у форматі YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")

        # 3. Підрахунок match_number за сьогодні
        all_rows = sheet.get_all_values()
        headers = all_rows[0]
        data_rows = all_rows[1:]

        date_index = headers.index("date") if "date" in headers else 1  # safety
        today_matches = [row for row in data_rows if len(row) > date_index and row[date_index] == today]
        match_number = len(today_matches) + 1

        # 4. Унікальний match_id (можна замінити на щось інше, якщо треба)
        match_id = str(uuid.uuid4())[:8]  # короткий UUID

        # 5. Порожні місця для середнього рейтингу
        avg_rate_team_1 = ""
        avg_rate_team_2 = ""

        # 6. Запис у таблицю
        row_to_add = [
            match_id,
            today,
            match_number,
            team1,
            team2,
            avg_rate_team_1,
            avg_rate_team_2,
            score1,
            score2
        ]

        sheet.append_row(row_to_add)
        update.message.reply_text(f"✅ Збережено результат: {team1} {score1} — {team2} {score2} (матч #{match_number} за {today})")

    except Exception as e:
        update.message.reply_text(f"⚠️ Помилка: {e}\nСпробуй у форматі: /result Команда1 2 - Команда2 1")

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

