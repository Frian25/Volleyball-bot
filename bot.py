import os
import json
import logging
import gspread
import uuid
import math
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
import io

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

# Отримуємо таблицю
try:
    sheet = client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
    ).worksheet("Matches")
except Exception as e:
    logging.error(f"Помилка підключення до таблиці: {e}")
    sheet = None

# Константи для рейтингової системи
INITIAL_RATING = 1500
MAX_K_FACTOR = 50
MIN_K_FACTOR = 15
STABILIZATION_GAMES = 25
HIGH_RATING_THRESHOLD = 1700
HIGH_RATING_K_MULTIPLIER = 0.8


def get_team_players(team_name, match_date):
    """Отримати список гравців команди на певну дату"""
    try:
        teams_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Teams")

        all_rows = teams_sheet.get_all_values()
        if len(all_rows) < 2:
            logging.warning("Таблиця Teams порожня або має тільки заголовки")
            return []

        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Знайти рядок з потрібною командою і датою
        for row in data_rows:
            if len(row) >= 3 and row[0] == match_date:  # date
                if row[1] == team_name:  # team_1
                    players = row[2].split(', ') if row[2] else []
                    return [player.strip() for player in players if player.strip()]
                elif len(row) >= 6 and row[4] == team_name:  # team_2
                    players = row[5].split(', ') if row[5] else []
                    return [player.strip() for player in players if player.strip()]

        logging.warning(f"Не знайдено гравців для команди {team_name} на дату {match_date}")
        return []
    except Exception as e:
        logging.error(f"Помилка при отриманні гравців команди: {e}")
        return []


def get_current_ratings():
    """Отримати поточні рейтинги всіх гравців"""
    try:
        rating_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Rating")

        all_rows = rating_sheet.get_all_values()
        if len(all_rows) < 2:
            logging.info("Таблиця Rating порожня, повертаємо пустий словник")
            return {}

        headers = all_rows[0]
        last_row = all_rows[-1]

        ratings = {}
        for i in range(2, len(headers)):  # Пропустити match_id та date
            if i < len(headers):
                player_name = headers[i].strip()
                if player_name:
                    try:
                        rating = int(float(last_row[i])) if i < len(last_row) and last_row[i] else INITIAL_RATING
                    except (ValueError, IndexError):
                        rating = INITIAL_RATING
                    ratings[player_name] = rating

        return ratings
    except Exception as e:
        logging.error(f"Помилка при отриманні рейтингів: {e}")
        return {}

def get_player_rating_history(player_name):
    """Отримати історію рейтингу гравця"""
    try:
        rating_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Rating")

        all_rows = rating_sheet.get_all_values()
        if len(all_rows) < 2:
            return []

        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Знайти індекс стовпця гравця
        player_index = None
        for i, header in enumerate(headers):
            if header.strip() == player_name:
                player_index = i
                break

        if player_index is None:
            return []

        history = []
        for row in data_rows:
            if len(row) > max(1, player_index):
                try:
                    date_str = row[1]  # date column
                    rating = int(float(row[player_index])) if row[player_index] else INITIAL_RATING

                    # Перетворити дату у формат datetime
                    match_date = datetime.strptime(date_str, "%Y-%m-%d")
                    history.append((match_date, rating))
                except (ValueError, IndexError):
                    continue

        return history
    except Exception as e:
        logging.error(f"Помилка при отриманні історії рейтингу: {e}")
        return []


def create_rating_chart(player_name, history):
    """Створити графік динаміки рейтингу"""
    if not history:
        return None

    try:
        # Налаштування для підтримки українських символів
        plt.rcParams['font.family'] = 'DejaVu Sans'

        dates, ratings = zip(*history)

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, ratings, marker='o', linewidth=2, markersize=4, color='#2E86AB')

        # Додати лінію початкового рейтингу
        ax.axhline(y=INITIAL_RATING, color='red', linestyle='--', alpha=0.5,
                   label=f'Початковий рейтинг ({INITIAL_RATING})')

        # Налаштування осей
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Рейтинг', fontsize=12)
        ax.set_title(f'Динаміка рейтингу: {player_name}', fontsize=14, fontweight='bold')

        # Форматування дат на осі X
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.xticks(rotation=45)

        # Сітка
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Покращити вигляд
        plt.tight_layout()

        # Зберегти у байт-буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer
    except Exception as e:
        logging.error(f"Помилка створення графіка: {e}")
        return None


def calculate_expected_score(rating_a, rating_b):
    """Розрахунок очікуваного результату (ELO формула)"""
    try:
        return 1 / (1 + pow(10, (rating_b - rating_a) / 400))
    except (OverflowError, ZeroDivisionError):
        return 0.5  # Якщо різниця рейтингів дуже велика


def get_score_multiplier(winner_score, loser_score):
    """Розрахунок множника на основі рахунку"""
    if winner_score <= 0 or loser_score < 0:
        return 1.0

    difference = winner_score - loser_score
    if difference >= 8:
        return 1.5  # Розгромна перемога
    elif difference >= 5:
        return 1.2  # Впевнена перемога
    elif difference >= 3:
        return 1.0  # Напружена перемога
    else:
        return 0.8  # Дуже напружена перемога


def get_team_average_rating(team_players, current_ratings):
    """Розрахунок середнього рейтингу команди"""
    if not team_players:
        return INITIAL_RATING

    total_rating = 0
    valid_players = 0

    for player in team_players:
        if player in current_ratings:
            total_rating += current_ratings[player]
            valid_players += 1
        else:
            # Для нових гравців використовуємо початковий рейтинг
            total_rating += INITIAL_RATING
            valid_players += 1

    return total_rating / valid_players if valid_players > 0 else INITIAL_RATING


def calculate_dynamic_k_factor(games_played, player_rating=None):
    """Розрахунок динамічного K-фактора"""
    if games_played == 0:
        return MAX_K_FACTOR

    decay_rate = STABILIZATION_GAMES / 3
    k_factor = MIN_K_FACTOR + (MAX_K_FACTOR - MIN_K_FACTOR) * math.exp(-games_played / decay_rate)

    # Додаткова корекція для високо рейтингових гравців
    if player_rating and player_rating > HIGH_RATING_THRESHOLD:
        k_factor *= HIGH_RATING_K_MULTIPLIER

    return round(k_factor, 1)


def get_player_games_count(player_name):
    """Отримати кількість зіграних матчів для гравця"""
    try:
        # Отримуємо дані з таблиці Matches для точного підрахунку
        matches_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Matches")

        teams_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Teams")

        matches_rows = matches_sheet.get_all_values()
        teams_rows = teams_sheet.get_all_values()

        if len(matches_rows) < 2 or len(teams_rows) < 2:
            return 0

        games_count = 0

        # Для кожного матчу перевіряємо чи брав участь гравець
        for match_row in matches_rows[1:]:  # Пропускаємо заголовки
            if len(match_row) >= 2:  # match_id, date
                match_date = match_row[1]

                # Шукаємо склади команд на цю дату
                for team_row in teams_rows[1:]:
                    if len(team_row) >= 6 and team_row[0] == match_date:
                        # Перевіряємо team_1_players та team_2_players
                        team1_players = team_row[2].split(', ') if team_row[2] else []
                        team2_players = team_row[5].split(', ') if len(team_row) > 5 and team_row[5] else []

                        # Очищаємо імена від пробілів
                        team1_players = [p.strip() for p in team1_players if p.strip()]
                        team2_players = [p.strip() for p in team2_players if p.strip()]

                        # Якщо гравець був у будь-якій команді в цьому матчі
                        if player_name in team1_players or player_name in team2_players:
                            games_count += 1
                            break  # Знайшли участь у цьому матчі, переходимо до наступного

        return games_count
    except Exception as e:
        logging.error(f"Помилка отримання кількості ігор для {player_name}: {e}")
        return 0


def calculate_new_rating_with_dynamic_k(old_rating, actual_score, expected_score, games_played, score_multiplier):
    """Обчислення нового рейтингу з динамічним K-фактором"""
    k_factor = calculate_dynamic_k_factor(games_played, old_rating)
    change = k_factor * (actual_score - expected_score) * score_multiplier
    new_rating = old_rating + change

    # Обмеження рейтингу (не може бути менше 100)
    new_rating = max(100, new_rating)

    return round(new_rating)


def update_rating_table(match_id, match_date, team1, team2, score1, score2):
    """Оновлення таблиці Rating з динамічним K-фактором"""
    try:
        rating_sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
        ).worksheet("Rating")

        # Отримати гравців для обох команд
        team1_players = get_team_players(team1, match_date)
        team2_players = get_team_players(team2, match_date)

        if not team1_players or not team2_players:
            logging.warning(f"Не знайдено гравців для команд {team1} і {team2} на дату {match_date}")
            return []

        # Отримати поточні рейтинги
        current_ratings = get_current_ratings()

        # Додати нових гравців з початковим рейтингом (тільки тих, хто грав)
        playing_players = set(team1_players + team2_players)
        for player in playing_players:
            if player not in current_ratings:
                current_ratings[player] = INITIAL_RATING

        # Отримати заголовки таблиці Rating
        rating_headers = rating_sheet.row_values(1) if rating_sheet.row_values(1) else []

        # Якщо заголовків немає, створити їх
        if not rating_headers:
            headers = ['match_id', 'date'] + sorted(current_ratings.keys())
            rating_sheet.append_row(headers)
            rating_headers = headers

        # Додати нових гравців до заголовків якщо потрібно
        new_players = [player for player in playing_players if player not in rating_headers]
        if new_players:
            rating_headers.extend(sorted(new_players))
            rating_sheet.update('1:1', [rating_headers])

        # Розрахувати середні рейтинги команд
        avg_rating_team1 = get_team_average_rating(team1_players, current_ratings)
        avg_rating_team2 = get_team_average_rating(team2_players, current_ratings)

        # Очікувані результати
        expected_team1 = calculate_expected_score(avg_rating_team1, avg_rating_team2)
        expected_team2 = 1 - expected_team1

        # Фактичні результати
        if score1 > score2:
            actual_team1, actual_team2 = 1, 0
        elif score2 > score1:
            actual_team1, actual_team2 = 0, 1
        else:
            actual_team1, actual_team2 = 0.5, 0.5  # Нічия

        # Множник на основі рахунку
        if score1 != score2:
            multiplier = get_score_multiplier(max(score1, score2), min(score1, score2))
        else:
            multiplier = 1.0

        # Створити копію поточних рейтингів для оновлення
        new_ratings = current_ratings.copy()
        changes = []

        # Оновити рейтинги ТІЛЬКИ гравців команди 1 (які грали)
        for player in team1_players:
            old_rating = new_ratings.get(player, INITIAL_RATING)
            games_played = get_player_games_count(player)

            new_rating = calculate_new_rating_with_dynamic_k(
                old_rating, actual_team1, expected_team1, games_played, multiplier
            )

            new_ratings[player] = new_rating
            k_factor = calculate_dynamic_k_factor(games_played, old_rating)

            change = new_rating - old_rating
            changes.append(f"{player}: {old_rating}→{new_rating} ({change:+d}) [K={k_factor:.1f}]")

        # Оновити рейтинги ТІЛЬКИ гравців команди 2 (які грали)
        for player in team2_players:
            old_rating = new_ratings.get(player, INITIAL_RATING)
            games_played = get_player_games_count(player)

            new_rating = calculate_new_rating_with_dynamic_k(
                old_rating, actual_team2, expected_team2, games_played, multiplier
            )

            new_ratings[player] = new_rating
            k_factor = calculate_dynamic_k_factor(games_played, old_rating)

            change = new_rating - old_rating
            changes.append(f"{player}: {old_rating}→{new_rating} ({change:+d}) [K={k_factor:.1f}]")

        # Підготувати рядок для додавання
        row_to_add = [match_id, match_date]

        # Для кожного гравця в заголовках
        for i in range(2, len(rating_headers)):
            player_name = rating_headers[i]
            if player_name in new_ratings:
                row_to_add.append(new_ratings[player_name])
            else:
                # Якщо гравець не грав у цьому матчі, беремо його попередній рейтинг
                if player_name in current_ratings:
                    row_to_add.append(current_ratings[player_name])
                else:
                    row_to_add.append(INITIAL_RATING)

        # Додати рядок до таблиці Rating
        rating_sheet.append_row(row_to_add)
        logging.info(f"Додано рядок до Rating для матчу {match_id} (оновлено тільки гравців які грали)")

        return changes

    except Exception as e:
        logging.error(f"Помилка при оновленні таблиці Rating: {e}")
        return []


def stats(update, context):
    """Команда для перегляду статистики гравця з графіком"""
    try:
        if not context.args:
            update.message.reply_text("⚠️ Використання: /stats ІмяГравця")
            return
        if update.message.chat.type != 'private':
            update.message.reply_text("⚠️ Ого, маєш гарні яйця, але таким краще не хвастатись при всіх, го в лс")
            return

        player_name = " ".join(context.args)
        current_ratings = get_current_ratings()

        if player_name not in current_ratings:
            update.message.reply_text(f"⚠️ Гравець '{player_name}' не знайдений")
            return

        current_rating = current_ratings[player_name]
        games_played = get_player_games_count(player_name)
        k_factor = calculate_dynamic_k_factor(games_played, current_rating)

        # Визначити статус
        if games_played < 5:
            status = "🔥 Новачок (швидка адаптація)"
        elif games_played < 15:
            status = "📈 Адаптується"
        elif games_played < 25:
            status = "📊 Стабілізується"
        else:
            status = "✅ Стабільний"

        message = f"📊 Статистика гравця: {player_name}\n"
        message += f"🏆 Поточний рейтинг: {current_rating}\n"
        message += f"🎮 Зіграно матчів: {games_played}\n"
        message += f"⚡ K-фактор: {k_factor}\n"
        message += f"📈 Статус: {status}\n"

        if games_played < 25:
            remaining_games = 25 - games_played
            message += f"\n💡 До повної стабілізації: {remaining_games} матчів"

        update.message.reply_text(message)

        # Створити та відправити графік
        if games_played > 0:
            history = get_player_rating_history(player_name)
            if history:
                chart_buffer = create_rating_chart(player_name, history)
                if chart_buffer:
                    chart_buffer.seek(0)
                    update.message.reply_photo(
                        photo=chart_buffer,
                        caption=f"📈 Динаміка рейтингу: {player_name}"
                    )

    except Exception as e:
        logging.error(f"Помилка в команді stats: {e}")
        update.message.reply_text(f"⚠️ Помилка: {e}")


def leaderboard(update, context):
    """Команда для перегляду топ гравців"""
    try:
        current_ratings = get_current_ratings()

        if not current_ratings:
            update.message.reply_text("⚠️ Немає даних про рейтинги")
            return

        # Сортувати за рейтингом
        sorted_players = sorted(current_ratings.items(), key=lambda x: x[1], reverse=True)

        message = "🏆 Топ гравців:\n\n"
        for i, (player, rating) in enumerate(sorted_players[:10], 1):
            games = get_player_games_count(player)
            if i == 1:
                message += f"👑 {player}: {rating} ({games} ігор)\n"
            elif i <= 3:
                message += f"🥉 {player}: {rating} ({games} ігор)\n"
            else:
                message += f"{i}. {player}: {rating} ({games} ігор)\n"

        update.message.reply_text(message)

    except Exception as e:
        logging.error(f"Помилка в команді leaderboard: {e}")
        update.message.reply_text(f"⚠️ Помилка: {e}")


def result(update, context):
    """Команда для додавання результату матчу"""
    try:
        if update.message.chat.type == 'private':
            update.message.reply_text("⚠️ Ти кого хочеш наїбати? Напиши в групу хай всі побачать.")
            return

        # Об'єднуємо аргументи у рядок
        text = " ".join(context.args)

        if "-" not in text:
            update.message.reply_text("⚠️ Команда має містити '-' між командами")
            return

        part1, part2 = [part.strip() for part in text.split("-", 1)]

        # В part1 останнє слово — рахунок1, все інше — команда1
        tokens1 = part1.rsplit(" ", 1)
        if len(tokens1) != 2:
            update.message.reply_text("⚠️ Не вдалося розпізнати команду 1 і рахунок")
            return

        team1 = tokens1[0].strip()
        try:
            score1 = int(tokens1[1])
        except ValueError:
            update.message.reply_text("⚠️ Рахунок команди 1 має бути числом")
            return

        # В part2 перше слово — рахунок2, все інше — команда2
        tokens2 = part2.split(" ", 1)
        if len(tokens2) != 2:
            update.message.reply_text("⚠️ Не вдалося розпізнати рахунок і команду 2")
            return

        try:
            score2 = int(tokens2[0])
        except ValueError:
            update.message.reply_text("⚠️ Рахунок команди 2 має бути числом")
            return

        team2 = tokens2[1].strip()

        if not team1 or not team2:
            update.message.reply_text("⚠️ Назви команд не можуть бути пустими")
            return

        # Поточна дата
        today = datetime.now().strftime("%Y-%m-%d")

        # Отримати всі дані з таблиці
        all_rows = sheet.get_all_values()
        if not all_rows:
            update.message.reply_text("⚠️ Помилка доступу до таблиці")
            return

        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Знайти індекс стовпця з датою
        date_index = headers.index("date") if "date" in headers else 1

        # Порахувати матчі сьогодні
        today_matches = [row for row in data_rows if len(row) > date_index and row[date_index] == today]
        match_number = len(today_matches) + 1

        # Унікальний match_id
        match_id = str(uuid.uuid4())[:8]

        # Додати переможця
        if score1 > score2:
            winner = team1
        elif score2 > score1:
            winner = team2
        else:
            winner = "Нічия"

        # Запис у таблицю
        row_to_add = [match_id, today, match_number, team1, team2, score1, score2, winner]

        # Додати стовпці якщо потрібно
        while len(row_to_add) > len(headers):
            headers.append(f"col_{len(headers)}")

        sheet.append_row(row_to_add)

        # Оновити таблицю Rating
        rating_changes = update_rating_table(match_id, today, team1, team2, score1, score2)

        # Підсумковий рахунок за сьогодні
        wins = {}
        for row in today_matches:
            if len(row) > 7 and row[7] and row[7] != "Нічия":
                winner_team = row[7]
                wins[winner_team] = wins.get(winner_team, 0) + 1

        # Додати поточний матч
        if winner != "Нічия":
            wins[winner] = wins.get(winner, 0) + 1

        # Сформувати відповідь
        message = f"✅ Збережено результат: {team1} {score1} — {score2} {team2}\n"
        message += f"🏆 Переможець: {winner}\n"
        message += f"📅 Матч #{match_number} за {today}\n"

        if wins:
            message += f"\n📊 Перемоги за сьогодні:\n"
            for team, count in sorted(wins.items(), key=lambda x: x[1], reverse=True):
                message += f"  {team}: {count}\n"


        update.message.reply_text(message)

    except Exception as e:
        logging.error(f"Помилка в команді result: {e}")
        update.message.reply_text(f"⚠️ Помилка: {e}\n"
                                  f"Спробуйте формат: /result Команда1 рахунок1 - рахунок2 Команда2")


def delete(update, context):
    """Команда для видалення останнього матчу"""
    try:
        if update.message.chat.type == 'private':
            update.message.reply_text("⚠️ Ти кого хочеш наїбати? Напиши в групу хай всі побачать.    ")
            return

        # Отримати всі рядки
        all_rows = sheet.get_all_values()
        if len(all_rows) <= 1:
            update.message.reply_text("⚠️ У таблиці немає даних для видалення.")
            return

        headers = all_rows[0]
        data_rows = all_rows[1:]
        date_index = headers.index("date") if "date" in headers else 1

        today = datetime.now().strftime("%Y-%m-%d")

        # Знайти індекси рядків за сьогодні
        deletable_indices = []
        for i, row in enumerate(data_rows):
            if len(row) > date_index and row[date_index] == today:
                deletable_indices.append(i + 2)  # +2 для правильної індексації

        if not deletable_indices:
            update.message.reply_text("⚠️ Немає записів за сьогодні для видалення.")
            return

        # Видалити останній рядок
        last_row_index = deletable_indices[-1]
        sheet.delete_rows(last_row_index)

        # Видалити з таблиці Rating
        try:
            rating_sheet = client.open_by_url(
                "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit?gid=1122235250#gid=1122235250"
            ).worksheet("Rating")

            rating_rows = rating_sheet.get_all_values()
            if len(rating_rows) > 1:
                rating_sheet.delete_rows(len(rating_rows))
                logging.info("Видалено останній рядок з Rating")

        except Exception as e:
            logging.error(f"Помилка при видаленні з Rating: {e}")

        update.message.reply_text("✅ Видалено останній матч з обох таблиць.")

    except Exception as e:
        logging.error(f"Помилка в команді delete: {e}")
        update.message.reply_text(f"⚠️ Помилка при видаленні: {e}")


def help_command(update, context):
    """Команда допомоги"""
    help_text = """
🏐 Команди волейбольного бота:

/result Команда1 рахунок1 - рахунок2 Команда2
   Приклад: /result Сині 15 - 10 Червоні

/stats ІмяГравця
   Приклад: /stats Олексій

/leaderboard - показати топ гравців

/delete - видалити останній матч (тільки сьогодні)

/help - показати цю допомогу

📊 Система рейтингів:
• Початковий рейтинг: 1500
• Новачки мають високий K-фактор (швидше змінюється рейтинг)
• Враховується сила суперника та різниця в рахунку
• Рейтинг змінюється ТІЛЬКИ у гравців які фактично грали
• Матчі зараховуються тільки тим, хто брав участь

"""
    update.message.reply_text(help_text)


# Ініціалізація бота
bot_token = os.environ.get("BOT_TOKEN")
if not bot_token:
    raise ValueError("BOT_TOKEN не знайдено в змінних середовища")

bot = Bot(token=bot_token)


# Налаштування диспетчера
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("result", result))
dispatcher.add_handler(CommandHandler("delete", delete))
dispatcher.add_handler(CommandHandler("stats", stats))
dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("start", help_command))


# Webhook endpoint
@app.route(f'/{bot_token}', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if not json_data:
            return 'No data', 400

        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)

        return 'OK'
    except Exception as e:
        logging.error(f"Помилка webhook: {e}")
        return 'ERROR', 500


# Health check endpoint
@app.route('/', methods=['GET'])
def health():
    return 'Volleyball Rating Bot is running! 🏐'


@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'healthy', 'service': 'volleyball-rating-bot'}


# Налаштування webhook при запуску
def setup_webhook():
    try:
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{bot_token}"
        bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook встановлено на: {webhook_url}")
    except Exception as e:
        logging.error(f"Помилка встановлення webhook: {e}")


if __name__ == "__main__":
    # Встановити webhook
    setup_webhook()

    # Запустити Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)