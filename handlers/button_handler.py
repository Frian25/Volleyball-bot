from telegram import Update
from telegram.ext import CallbackContext

from services.sheets import spreadsheet
from handlers.generate_teams import generate_teams, pending_teams


def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id

    if chat_id not in pending_teams:
        query.edit_message_text("⚠️ Teams not found or already confirmed.")
        return

    data = pending_teams[chat_id]

    if query.data == "confirm_teams":
        teams_worksheet = spreadsheet.worksheet("Teams")
        header = teams_worksheet.row_values(1)
        row = {"date": data["date"]}

        for i, team in enumerate(data["teams"]):
            row[f"team {i + 1}"] = data["team_names"][i]
            row[f"team {i + 1}_players"] = ", ".join([p for p, _ in team])
            row[f"avg_rate_team {i + 1}"] = round(data["sums"][i] / data["counts"][i] / 100, 2)

        row_data = [row.get(col, "") for col in header]
        teams_worksheet.append_row(row_data)

        query.edit_message_text("✅ Teams confirmed and saved.")

        text = f"📅 Confirmed teams for {data['date']}:\n"
        for i, team in enumerate(data["teams"]):
            text += f"\n🏐 *Team {i + 1}* ({data['team_names'][i]}):\n"
            for name, _ in team:
                text += f"• {name}\n"
            avg = round(data["sums"][i] / data["counts"][i] / 100, 2)
            text += f"Average rating: {avg}_\n"

        context.bot.send_message(chat_id, text, parse_mode="Markdown")
        context.bot.send_message(chat_id, "🎉 Good luck in the match!")
        pending_teams.pop(chat_id)

    elif query.data == "regenerate_teams":
        context.bot.delete_message(chat_id, query.message.message_id)
        fake_update = type("Fake", (), {"message": query.message, "args": [data["date"]]})
        context.args = [data["date"], str(len(data["teams"]))]
        generate_teams(fake_update, context)
