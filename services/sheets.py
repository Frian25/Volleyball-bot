import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDS_JSON, SPREADSHEET_URL

# Авторизація через Google Service Account
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_JSON, scope)
client = gspread.authorize(creds)

# Основна таблиця
spreadsheet = client.open_by_url(SPREADSHEET_URL)
final_score = spreadsheet.worksheet("Final Score")
rating_sheet = spreadsheet.worksheet("Rating")
match_sheet = spreadsheet.worksheet("Matches")
teams_sheet = spreadsheet.worksheet("Teams")
appeals_sheet = spreadsheet.worksheet("Appeals")
mvp_results_sheet = spreadsheet.worksheet("MVP Results")

# Прості кеші
cache = {
    "ratings": None,
    "ratings_time": 0,
    "matches_rows": None,
    "matches_time": 0,
    "teams_rows": None,
    "teams_time": 0,
}


# Отримати існуючі команди на дату
def get_existing_teams(date=None):
    try:
        all_rows = teams_sheet.get_all_values()
        headers = all_rows[0]
        data = all_rows[1:]

        team_names = set()
        for row in data:
            if not row:
                continue

            if date:
                date_idx = headers.index("date") if "date" in headers else 0
                if len(row) <= date_idx or row[date_idx] != date:
                    continue

            for i in range(1, 10):  # team_1, team_2, ..., team_9
                col_name = f"team_{i}"
                if col_name in headers:
                    idx = headers.index(col_name)
                    if idx < len(row) and row[idx]:
                        team_names.add(row[idx].strip())

        return team_names

    except Exception as e:
        print(f"Error while fetching existing teams: {e}")
        return set()
