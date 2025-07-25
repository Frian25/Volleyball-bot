import math
import time
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import io

from config import (
    INITIAL_RATING, MAX_K_FACTOR, MIN_K_FACTOR, STABILIZATION_GAMES,
    HIGH_RATING_THRESHOLD, HIGH_RATING_K_MULTIPLIER
)

from services.sheets import rating_sheet, teams_sheet, match_sheet, cache


def get_current_ratings():
    now = time.time()
    if cache["ratings"] and now - cache["ratings_time"] < 60:
        return cache["ratings"]

    all_rows = rating_sheet.get_all_values()
    if len(all_rows) < 2:
        return {}

    headers = all_rows[0]
    last_row = all_rows[-1]

    ratings = {}
    for i in range(2, len(headers)):
        player = headers[i].strip()
        if not player:
            continue
        try:
            value = int(float(last_row[i])) if i < len(last_row) and last_row[i] else INITIAL_RATING
        except:
            value = INITIAL_RATING
        ratings[player] = value

    cache["ratings"] = ratings
    cache["ratings_time"] = now
    return ratings


def get_player_games_count(player_name):
    now = time.time()

    if not cache["matches_rows"] or now - cache["matches_time"] > 60:
        cache["matches_rows"] = match_sheet.get_all_values()
        cache["matches_time"] = now

    if not cache["teams_rows"] or now - cache["teams_time"] > 60:
        cache["teams_rows"] = teams_sheet.get_all_values()
        cache["teams_time"] = now

    count = 0
    for match_row in cache["matches_rows"][1:]:
        if len(match_row) < 2:
            continue
        match_date = match_row[1]
        for team_row in cache["teams_rows"][1:]:
            if len(team_row) >= 6 and team_row[0] == match_date:
                players = team_row[2].split(", ") + team_row[5].split(", ")
                if player_name in [p.strip() for p in players if p.strip()]:
                    count += 1
                    break
    return count


def calculate_expected_score(rating_a, rating_b):
    return 1 / (1 + pow(10, (rating_b - rating_a) / 400))


def calculate_dynamic_k_factor(games_played, rating=None):
    if games_played == 0:
        return MAX_K_FACTOR
    decay = STABILIZATION_GAMES / 3
    k = MIN_K_FACTOR + (MAX_K_FACTOR - MIN_K_FACTOR) * math.exp(-games_played / decay)
    if rating and rating > HIGH_RATING_THRESHOLD:
        k *= HIGH_RATING_K_MULTIPLIER
    return round(k, 1)


def get_score_multiplier(winner, loser):
    diff = winner - loser
    if diff >= 8:
        return 1.5
    elif diff >= 5:
        return 1.2
    elif diff >= 3:
        return 1.0
    else:
        return 0.8


def get_team_players(team_name, match_date):
    all_rows = teams_sheet.get_all_values()
    for row in all_rows[1:]:
        if len(row) >= 6 and row[0] == match_date:
            if row[1] == team_name:
                return row[2].split(", ")
            elif row[4] == team_name:
                return row[5].split(", ")
    return []


def get_team_average_rating(players, ratings):
    if not players:
        return INITIAL_RATING
    total, count = 0, 0
    for player in players:
        total += ratings.get(player, INITIAL_RATING)
        count += 1
    return total / count if count else INITIAL_RATING


def get_last_game_date(player_name):
    now = time.time()

    if not cache["matches_rows"] or now - cache["matches_time"] > 60:
        cache["matches_rows"] = match_sheet.get_all_values()
        cache["matches_time"] = now

    if not cache["teams_rows"] or now - cache["teams_time"] > 60:
        cache["teams_rows"] = teams_sheet.get_all_values()
        cache["teams_time"] = now

    dates = []
    for row in cache["matches_rows"][1:]:
        if len(row) >= 2:
            match_date = row[1]
            for team_row in cache["teams_rows"][1:]:
                if len(team_row) >= 6 and team_row[0] == match_date:
                    players = team_row[2].split(", ") + team_row[5].split(", ")
                    if player_name in [p.strip() for p in players if p.strip()]:
                        dates.append(datetime.strptime(match_date, "%Y-%m-%d"))

    return max(dates) if dates else None


def calculate_new_rating(old, actual, expected, games, multiplier):
    k = calculate_dynamic_k_factor(games, old)
    delta = k * (actual - expected) * multiplier
    return max(100, round(old + delta))


def update_rating_table(match_id, match_date, team1, team2, score1, score2):
    dt = datetime.strptime(match_date, "%Y-%m-%d")
    team1_players = [p.strip() for p in get_team_players(team1, match_date)]
    team2_players = [p.strip() for p in get_team_players(team2, match_date)]
    current_ratings = get_current_ratings()

    for p in team1_players + team2_players:
        if p not in current_ratings:
            current_ratings[p] = INITIAL_RATING

    avg1 = get_team_average_rating(team1_players, current_ratings)
    avg2 = get_team_average_rating(team2_players, current_ratings)
    exp1 = calculate_expected_score(avg1, avg2)
    exp2 = 1 - exp1

    actual1, actual2 = 0.5, 0.5
    if score1 > score2:
        actual1, actual2 = 1, 0
    elif score2 > score1:
        actual1, actual2 = 0, 1

    multiplier = get_score_multiplier(max(score1, score2), min(score1, score2))

    new_ratings = current_ratings.copy()

    for player, actual, expected in zip(
        team1_players + team2_players,
        [actual1] * len(team1_players) + [actual2] * len(team2_players),
        [exp1] * len(team1_players) + [exp2] * len(team2_players)
    ):
        old = new_ratings.get(player, INITIAL_RATING)
        games = get_player_games_count(player)
        new_ratings[player] = calculate_new_rating(old, actual, expected, games, multiplier)

    # Зниження за неактивність
    for player in current_ratings:
        if player in team1_players + team2_players:
            continue
        last = get_last_game_date(player)
        if last:
            inactive_days = (dt - last).days
            if inactive_days > 16 and current_ratings[player] > INITIAL_RATING:
                new_ratings[player] = max(INITIAL_RATING, current_ratings[player] - 10)

    # Додаємо новий рядок у Rating
    headers = rating_sheet.row_values(1)
    if not headers:
        headers = ['match_id', 'date']
    for p in new_ratings:
        if p not in headers:
            headers.append(p)
    rating_sheet.update('1:1', [headers])

    row = [match_id, match_date]
    for p in headers[2:]:
        row.append(new_ratings.get(p, INITIAL_RATING))

    rating_sheet.append_row(row)
    return True


def get_player_rating_history(player_name):
    all_rows = rating_sheet.get_all_values()
    headers = all_rows[0]
    data_rows = all_rows[1:]

    index = None
    for i, col in enumerate(headers):
        if col == player_name:
            index = i
            break

    if index is None:
        return []

    history = []
    for row in data_rows:
        if len(row) > 1 and len(row) > index:
            date_str = row[1]
            rating = row[index]
            if rating:
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    history.append((date, int(float(rating))))
                except:
                    continue
    return history


def create_rating_chart(player_name, history):
    if not history:
        return None

    weekly = defaultdict(list)
    for date, rating in history:
        year, week, _ = date.isocalendar()
        weekly[(year, week)].append(rating)

    weeks = sorted(weekly.keys())
    labels, values = [], []

    for year, week in weeks:
        label = f"{year}-W{week}"
        ratings = weekly[(year, week)]
        avg = sum(ratings) / len(ratings)
        labels.append(label)
        values.append(avg)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(labels, values, marker='o', linewidth=2)
    ax.set_xlabel('Week')
    ax.set_ylabel('Rating')
    ax.set_title(f'Weekly Rating: {player_name}')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300)
    buf.seek(0)
    plt.close()
    return buf