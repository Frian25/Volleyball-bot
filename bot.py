import os
import json
import logging
import gspread
import uuid
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler

# Увімкнути логування
logging.basicConfig(level=logging.INFO)

# Flask додаток
app = Flask(__name__)

# Отримуємо JSON з ключами з середовища
creds_dict = json.loads(os.environ["CREDS_JSON"])

# Права доступу до Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250").worksheet(
    "Matches")


def get_team_players(team_name, match_date):
    """Отримати список гравців команди на певну дату"""
    try:
        teams_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250").worksheet(
            "Teams")

        all_rows = teams_sheet.get_all_values()
        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Знайти рядок з потрібною командою і датою
        for row in data_rows:
            if len(row) >= 3 and row[0] == match_date:  # date
                if row[1] == team_name:  # team_1
                    return row[2].split(', ') if row[2] else []  # team_1_players
                elif len(row) >= 5 and row[4] == team_name:  # team_2
                    return row[5].split(', ') if row[5] else []  # team_2_players

        return []
    except Exception as e:
        logging.error(f"Помилка при отриманні гравців команди: {e}")
        return []


def update_rating_table(match_id, match_date, team1, team2):
    """Оновити таблицю Rating з інформацією про участь гравців"""
    try:
        rating_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250").worksheet(
            "Rating")

        # Отримати гравців для обох команд
        team1_players = get_team_players(team1, match_date)
        team2_players = get_team_players(team2, match_date)

        all_players = team1_players + team2_players

        if not all_players:
            logging.warning(f"Не знайдено гравців для команд {team1} і {team2} на дату {match_date}")
            return

        # Отримати заголовки таблиці Rating
        rating_headers = rating_sheet.row_values(1)

        # Підготувати рядок для додавання
        row_to_add = [match_id, match_date]

        # Для кожного гравця в заголовках (починаючи з 3-го стовпця)
        for i in range(2, len(rating_headers)):
            player_name = rating_headers[i]
            # Поставити 1 якщо гравець брав участь, інакше 0
            row_to_add.append(1 if player_name in all_players else 0)

        # Додати рядок до таблиці Rating
        rating_sheet.append_row(row_to_add)
        logging.info(f"Додано рядок до Rating для матчу {match_id}")

    except Exception as e:
        logging.error(f"Помилка при оновленні таблиці Rating: {e}")


# Ініціалізація бота
bot_token = os.environ["BOT_TOKEN"]
bot = Bot(token=bot_token)


# Функція /result команда1 рахунок1 команда2 рахунок2
def result(update, context):
    try:
        if update.message.chat.type == 'private':
            update.message.reply_text("⚠️ Ти кого хочеш наїбати? Напиши в групу хай всі побачать.")
            return
        # Об'єднуємо аргументи у рядок
        text = " ".join(context.args)

        if "-" not in text:
            raise ValueError("Команда має містити '-'")

        part1, part2 = [part.strip() for part in text.split("-", 1)]

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

        # Запис у таблицю
        row_to_add = [
            match_id,
            today,
            match_number,
            team1,
            team2,
            score1,
            score2
        ]
        sheet.append_row(row_to_add)

        # ДОДАНО: Оновити таблицю Rating
        update_rating_table(match_id, today, team1, team2)

        # ПІДСУМКОВИЙ РАХУНОК ЗА СЬОГОДНІ
        wins = {}

        # Враховуємо попередні матчі
        for row in today_matches:
            if len(row) >= 7:
                winner = row[7]  # Припускаю, що переможець у 8-му стовпчику (індекс 7)
                if winner:  # Якщо не нічия і переможець є
                    wins[winner] = wins.get(winner, 0) + 1

        # Додаємо поточний матч
        if team1 != team2:  # перевіримо чи матч не між однією командою (на всяк випадок)
            if score1 > score2:
                wins[team1] = wins.get(team1, 0) + 1
            elif score2 > score1:
                wins[team2] = wins.get(team2, 0) + 1
            else:
                wins[team1] = wins.get(team1, 0) + 1
                wins[team2] = wins.get(team2, 0) + 1
            # нічия — нічого не додаємо

        # Сформуємо зручний вигляд підсумку
        summary = f"{team1} {wins.get(team1, 0)} — {wins.get(team2, 0)} {team2}"

        # Надсилання відповіді
        update.message.reply_text(
            f"✅ Збережено результат: {team1} {score1} — {team2} {score2} (матч #{match_number} за {today})\n"
            f"📊 Загальний рахунок: {summary}"
        )
    except Exception as e:
        update.message.reply_text(f"⚠️ Помилка: {e}\nСпробуй у форматі: /result Команда1 рахунок1 - рахунок2 Команда2")


def delete(update, context):
    try:
        # 🔒 Дозволити лише в групових чатах
        if update.message.chat.type == 'private':
            update.message.reply_text("⚠️ Ти кого хочеш наїбати? Напиши в групу, хай всі побачать.")
            return

        # Отримати всі рядки (включаючи заголовок)
        all_rows = sheet.get_all_values()
        if len(all_rows) <= 1:
            update.message.reply_text("⚠️ У таблиці немає даних для видалення.")
            return

        headers = all_rows[0]
        data_rows = all_rows[1:]
        date_index = headers.index("date") if "date" in headers else 1

        today = datetime.now().strftime("%Y-%m-%d")

        # Знайти всі індекси рядків, де date == today
        deletable_indices = [
            i + 2  # +2 бо 1-й рядок — заголовки, індексація з 1
            for i, row in enumerate(data_rows)
            if len(row) > date_index and row[date_index] == today
        ]

        if not deletable_indices:
            update.message.reply_text("⚠️ Немає записів за сьогодні для видалення.")
            return

        # Видалити всі знайдені рядки знизу вгору (щоб індекси не зміщувалися)
        sheet.delete_rows(deletable_indices[-1])

        update.message.reply_text(f"✅ Видалено останній добавлений рядок.")

    except Exception as e:
        update.message.reply_text(f"⚠️ Помилка при видаленні: {e}")


# Налаштування диспетчера
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("result", result))
dispatcher.add_handler(CommandHandler("delete", delete))


# Webhook endpoint
@app.route(f'/{bot_token}', methods=['POST'])
def webhook():
    try:
        # Отримати дані від Telegram
        json_data = request.get_json()

        # Обробити оновлення
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)

        return 'OK'
    except Exception as e:
        logging.error(f"Помилка webhook: {e}")
        return 'ERROR', 500


# Health check endpoint
@app.route('/', methods=['GET'])
def health():
    return 'Bot is running!'


# Налаштування webhook при запуску
def setup_webhook():
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{bot_token}"
    bot.set_webhook(url=webhook_url)
    logging.info(f"Webhook встановлено на: {webhook_url}")


if __name__ == "__main__":
    # Встановити webhook
    setup_webhook()

    # Запустити Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)