import uuid
from telegram import Update
from telegram.ext import CallbackContext

from services.sheets import match_sheet, get_existing_teams
from services.rating_logic import update_rating_table
from utils.misc import get_today_date, is_quota_exceeded_error


def result(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command is only for group chats.")
        return

    text = " ".join(context.args)

    if "-" not in text:
        update.message.reply_text("⚠️ Use format: Team1 score1 - score2 Team2")
        return

    part1, part2 = [p.strip() for p in text.split("-", 1)]

    tokens1 = part1.rsplit(" ", 1)
    if len(tokens1) != 2:
        update.message.reply_text("⚠️ Couldn't parse team 1 and its score.")
        return

    team1 = tokens1[0].strip()
    try:
        score1 = int(tokens1[1])
    except ValueError:
        update.message.reply_text("⚠️ Use format: Team1 score1 - score2 Team2")
        return

    tokens2 = part2.split(" ", 1)
    if len(tokens2) != 2:
        update.message.reply_text("⚠️ Couldn't parse team 2 and its score.")
        return

    try:
        score2 = int(tokens2[0])
    except ValueError:
        update.message.reply_text("⚠️ Use format: Team1 score1 - score2 Team2.")
        return

    team2 = tokens2[1].strip()

    if not team1 or not team2:
        update.message.reply_text("⚠️ Team names cannot be empty.")
        return

    today = get_today_date()

    try:
        all_rows = match_sheet.get_all_values()
    except Exception as e:
        update.message.reply_text("⚠️ Failed to access match sheet.")
        return

    existing_teams = get_existing_teams(today)
    if team1 not in existing_teams or team2 not in existing_teams:
        update.message.reply_text("⚠️ One or both teams not found for today.")
        return

    headers = all_rows[0] if all_rows else []
    data_rows = all_rows[1:]

    date_idx = headers.index("date") if "date" in headers else 1
    today_matches = [r for r in data_rows if len(r) > date_idx and r[date_idx] == today]
    match_number = len(today_matches) + 1
    match_id = str(uuid.uuid4())[:8]

    if score1 > score2:
        winner = team1
    elif score2 > score1:
        winner = team2
    else:
        winner = "Draw"

    row_to_add = [match_id, today, match_number, team1, team2, score1, score2, winner]

    while len(row_to_add) > len(headers):
        headers.append(f"col_{len(headers)}")

    try:
        match_sheet.append_row(row_to_add)
        rating_changes = update_rating_table(match_id, today, team1, team2, score1, score2)
    except Exception as e:
        if is_quota_exceeded_error(e):
            update.message.reply_text("❌ Google Sheets quota exceeded.")
        else:
            update.message.reply_text(f"⚠️ Error: {e}")
        return

    # Count team wins
    wins = {}
    for row in today_matches:
        if len(row) > 7 and row[7] and row[7] != "Draw":
            wins[row[7]] = wins.get(row[7], 0) + 1
    if winner != "Draw":
        wins[winner] = wins.get(winner, 0) + 1

    message = f"✅ Result saved: {team1} {score1} - {score2} {team2}\n"
    message += f"🏆 Winner: {winner}\n"
    message += f"📅 Match #{match_number} for {today}\n"

    if wins:
        message += "\n📊 Wins today:\n"
        for team, count in sorted(wins.items(), key=lambda x: x[1], reverse=True):
            message += f"  {team}: {count}\n"

    update.message.reply_text(message)
