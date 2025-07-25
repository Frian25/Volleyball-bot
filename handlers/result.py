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
        update.message.reply_text("⚠️ Score for team 1 must be a number.")
        return

    tokens2 = part2.split(" ", 1)
    if len(tokens2) != 2:
        update.message.reply_text("⚠️ Couldn't parse team 2 and its score.")
        return

    try:
        score2 = int(tokens2[0])
    except ValueError:
        update.message.reply_text("⚠️ Score for team 2 must be a number.")
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
