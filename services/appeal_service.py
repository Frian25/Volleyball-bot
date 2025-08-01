import uuid
from datetime import datetime
from collections import Counter

from services.sheets import spreadsheet, teams_sheet, match_sheet, rating_sheet, appeals_sheet, mvp_results_sheet
from services.rating_logic import get_player_games_count


def can_create_appeal_today(date):
    """Перевіряє, чи можна створити апеляцію сьогодні (одна на день)"""
    try:
        all_rows = appeals_sheet.get_all_values()

        if len(all_rows) <= 1:  # Тільки заголовки або пусто
            return True

        # Перевіряємо, чи є запис на сьогодні
        for row in all_rows[1:]:
            if len(row) >= 2 and row[1] == date:
                return False

        return True
    except Exception as e:
        print(f"Error while checking appeal eligibility: {e}")
        return False


def is_appeal_active(date):
    """Перевіряє, чи є активна апеляція на дату"""
    try:
        appeals_sheet
        all_rows = appeals_sheet.get_all_values()

        for row in all_rows[1:]:
            if len(row) >= 6 and row[1] == date and row[5] == 'active':
                return True

        return False
    except Exception as e:
        print(f"Error while checking appeal eligibility: {e}")
        return False


def get_today_teams_and_players(date):
    """Отримує команди та їх гравців на вказану дату"""
    try:
        all_rows = teams_sheet.get_all_values()
        if len(all_rows) <= 1:
            return {}

        headers = all_rows[0]
        teams_data = {}

        # Шукаємо рядок з потрібною датою
        for row in all_rows[1:]:
            if len(row) >= 1 and row[0] == date:
                # Перебираємо всі можливі команди (team_1, team_2, ...)
                for i in range(1, 10):  # до 9 команд
                    team_col = f"team_{i}"
                    players_col = f"team_{i}_players"

                    if team_col in headers and players_col in headers:
                        team_idx = headers.index(team_col)
                        players_idx = headers.index(players_col)

                        if (team_idx < len(row) and players_idx < len(row) and
                                row[team_idx] and row[players_idx]):

                            team_name = row[team_idx].strip()
                            players_str = row[players_idx].strip()

                            if team_name and players_str:
                                players = [p.strip() for p in players_str.split(',') if p.strip()]
                                if players:
                                    teams_data[team_name] = players

        return teams_data
    except Exception as e:
        print(f"Error while retrieving teams and players: {e}")
        return {}


def create_appeal_record(date, teams_data):
    """Створює запис про апеляцію та повертає її ID"""
    appeal_id = str(uuid.uuid4())[:8]

def process_poll_results(poll_id, poll_results):
    """Обробляє результати голосування після його завершення"""
    try:
        appeals_sheet
        all_rows = appeals_sheet.get_all_values()

        # Знаходимо рядок з цим poll_id
        target_row_idx = None
        team_name = None
        date = None

        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) >= 4 and row[3] == poll_id:
                target_row_idx = i
                team_name = row[2]
                date = row[1]
                break

        if not target_row_idx:
            print(f"No record found for poll_id.: {poll_id}")
            return

        # Аналізуємо результати голосування
        total_votes = sum(poll_results.values())

        if total_votes < 6:
            # Недостатньо голосів
            result_text = f"insufficient_votes_{total_votes}"
            appeals_sheet.update_cell(target_row_idx, 7, 'completed')  # status
            appeals_sheet.update_cell(target_row_idx, 9, result_text)  # results
            return

        # Перевіряємо, чи є гравець з 66%+ голосів
        winner = None
        max_votes = max(poll_results.values())
        win_percentage = (max_votes / total_votes) * 100

        if win_percentage >= 66:
            # Знаходимо переможця
            for player, votes in poll_results.items():
                if votes == max_votes:
                    winner = player
                    break

        if winner:
            # Нараховуємо бонусні бали
            bonus_applied = apply_bonus_rating(winner, date)
            result_text = f"winner_{winner}_votes_{max_votes}_total_{total_votes}_bonus_{bonus_applied}"
        else:
            result_text = f"no_winner_max_{max_votes}_total_{total_votes}_percent_{win_percentage:.1f}"

        # Оновлюємо статус та результати
        appeals_sheet.update_cell(target_row_idx, 6, 'completed')  # status
        appeals_sheet.update_cell(target_row_idx, 7, result_text)  # results

        return winner

    except Exception as e:
        print(f"Error while processing poll results: {e}")
        return None


def apply_bonus_rating(player_name, date):
    """Застосовує бонусні бали до рейтингу гравця"""
    try:
        # Отримуємо кількість матчів, зіграних гравцем сьогодні
        matches_today = get_player_matches_today(player_name, date)

        if matches_today == 0:
            return 0

        bonus_points = 3 * matches_today

        # Оновлюємо рейтинг у таблиці Rating
        rating_rows = rating_sheet.get_all_values()
        headers = rating_rows[0]

        # Знаходимо колонку гравця
        player_col_idx = None
        for i, header in enumerate(headers):
            if header.strip() == player_name:
                player_col_idx = i
                break

        if player_col_idx is None:
            print(f"Player {player_name} didn't find in the rating sheet.")
            return 0

        # Знаходимо останній рядок з рейтингом
        last_row_idx = len(rating_rows)
        current_rating = rating_rows[-1][player_col_idx] if rating_rows[-1][player_col_idx] else 1500
        new_rating = int(current_rating) + bonus_points

        # Оновлюємо рейтинг
        rating_sheet.update_cell(last_row_idx, player_col_idx + 1, new_rating)

        # Записуємо інформацію в MVP Results
        save_mvp_result(player_name, date, matches_today, bonus_points, current_rating, new_rating)

        return bonus_points

    except Exception as e:
        print(f"Error while applying bonus points.: {e}")
        return 0


def get_player_matches_today(player_name, date):
    """Отримує кількість матчів, зіграних гравцем сьогодні"""
    try:
        matches_rows = match_sheet.get_all_values()
        teams_rows = teams_sheet.get_all_values()

        if len(matches_rows) <= 1 or len(teams_rows) <= 1:
            return 0

        matches_today = 0

        # Перевіряємо кожен матч сьогодні
        for match_row in matches_rows[1:]:
            if len(match_row) >= 2 and match_row[1] == date:
                # Знаходимо команди для цього матчу
                for team_row in teams_rows[1:]:
                    if len(team_row) >= 6 and team_row[0] == date:
                        team1_players = [p.strip() for p in team_row[2].split(',') if p.strip()]
                        team2_players = [p.strip() for p in team_row[5].split(',') if p.strip()]

                        if player_name in team1_players or player_name in team2_players:
                            matches_today += 1
                            break

        return matches_today

    except Exception as e:
        print(f"Error while counting player's matches: {e}")
        return 0


def save_mvp_result(player_name, date, matches_count, bonus_points, old_rating, new_rating):
    """Зберігає результат MVP у таблицю MVP Results"""
    try:
        # Додаємо новий запис
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mvp_results_sheet.append_row([
            date,
            player_name,
            matches_count,
            bonus_points,
            old_rating,
            new_rating,
            timestamp
        ])

    except Exception as e:
        print(f"Error while counting player's matches: {e}")