import random
import pandas as pd
from services.sheets import spreadsheet
from config import INCOMPATIBLE_PAIRS


def get_team_candidates():
    """
    Отримати гравців з листа 'Final Score', які позначені як is_ready == 1
    """
    try:
        sheet = spreadsheet.worksheet("Final Score")
        df = pd.DataFrame(sheet.get_all_records())
        df = df.query("is_ready == 1")

        # перевіримо наявність потрібних колонок
        if "Player Name" not in df.columns or "Rating for Team Matching" not in df.columns:
            raise ValueError("Missing required columns in 'Final Score' sheet")

        return list(zip(df["Player Name"], df["Rating for Team Matching"]))
    except Exception as e:
        print(f"❌ Error loading players from Final Score: {e}")
        return []



def violates_restriction(team, forbidden_pairs):
    names = {name for name, _ in team}
    return any(a in names and b in names for a, b in forbidden_pairs)


def regenerate_teams_logic(players, num_teams=2, max_difference=20):
    """
    Розподіляє гравців на збалансовані команди
    """
    max_players_per_team = len(players) // num_teams

    while True:
        teams = [[] for _ in range(num_teams)]
        team_sums = [0] * num_teams
        team_counts = [0] * num_teams

        random.shuffle(players)

        for name, score in players:
            best_team = None
            min_diff = float("inf")

            for i in range(num_teams):
                if team_counts[i] >= max_players_per_team:
                    continue

                teams[i].append((name, score))

                if not violates_restriction(teams[i], INCOMPATIBLE_PAIRS):
                    temp_sums = team_sums[:]
                    temp_sums[i] += score
                    diff = max(temp_sums) - min(temp_sums)

                    if diff < min_diff and diff <= max_difference:
                        min_diff = diff
                        best_team = i

                teams[i].pop()

            if best_team is None:
                best_team = team_counts.index(min(team_counts))

            teams[best_team].append((name, score))
            team_sums[best_team] += score
            team_counts[best_team] += 1

        avg_scores = [team_sums[i] / team_counts[i] for i in range(num_teams)]
        if abs(max(avg_scores) - min(avg_scores)) <= max_difference:
            if all(not violates_restriction(t, INCOMPATIBLE_PAIRS) for t in teams):
                return teams, team_sums, team_counts
