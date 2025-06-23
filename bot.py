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
        # Об'єднуємо аргументи у рядок, наприклад:
        # "Команда1 2 - 1 Команда2"
        text = " ".join(context.args)

        if "-" not in text:
            raise ValueError("Формат має бути: Команда1 рахунок1 - рахунок2 Команда2")

        part1, part2 = [part.strip() for part in text.split("-", 1)]

        # part1: "Команда1 2"
        # part2: "1 Команда2"

        # В part1 останнє слово — рахунок1, все інше — команда1
        tokens1 = part1.rsplit(" ", 1)
        if len(tokens1) != 2:
            raise ValueError("Не вдалося розпізнати команду 1 і рахунок")
        team1 = tokens1[0]
        score1 = int(tokens1[1])

        # В part2 перше слово — рахунок2, все інше — команда2
        tokens2 = part2.split(" ", 1)
        if len(tokens2) != 2:
            raise ValueError("Не вдалося розпізнати рахунок і команду 2")
        score2 = int(tokens2[0])
        team2 = tokens2[1]

        # Поточна дата YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")

        # Отримаємо всі дані з таблиці
        all_rows = sheet.get_all_values()
        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Знайдемо індекс стовпця з датою
        date_index = headers.index("date") if "date" in headers else 1

        # Порахувати матчі сьогодні
        today_matches = [row for row in data_rows if len(row) > date_index and row[date_index] == today]
        match_number = len(today_matches) + 1

        # Унікальний match_id
        match_id = str(uuid.uuid4())[:8]

        # Порожні avg_rate
        avg_rate_team_1 = ""
        avg_rate_team_2 = ""

        # Запис у таблицю
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
        update.message.reply_text(f"⚠️ Помилка: {e}\nСпробуй у форматі: /result Команда1 рахунок1 - рахунок2 Команда2")

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

