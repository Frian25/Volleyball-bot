from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from faker import Faker

from services.team_balancer import get_team_candidates, regenerate_teams_logic
from config import INCOMPATIBLE_PAIRS

faker = Faker("en_US")  # ⚠️ faker тепер англійською
pending_teams = {}

# 🔁 Команда генерації команд
def generate_teams(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        context.bot.send_message(update.message.chat_id, "⚠️ This command can only be used in a group.")
        return

    if not context.args:
        context.bot.send_message(update.message.chat_id, "⚠️ Please provide the date: /generate_teams YYYY-MM-DD [number_of_teams]")
        return

    game_date = context.args[0]

    try:
        num_teams = int(context.args[1]) if len(context.args) > 1 else 2
        if num_teams < 2:
            context.bot.send_message(update.message.chat_id, "⚠️ The minimum number of teams is 2.")
            return
    except ValueError:
        context.bot.send_message(update.message.chat_id, "⚠️ Number of teams must be an integer.")
        return

    players = get_team_candidates()
    if not players:
        context.bot.send_message(update.message.chat_id, "⚠️ No players are marked as ready.")
        return

    teams, team_sums, team_counts = regenerate_teams_logic(players, num_teams=num_teams)
    team_names = [faker.word() for _ in range(num_teams)]  # англомовні назви

    text = f"📅 Teams for {game_date}:\n"
    for i, team in enumerate(teams):
        text += f"\n🏐 *Team {i + 1}* ({team_names[i]}):\n"
        for name, _ in team:
            text += f"• {name}\n"
        avg_score = round(team_sums[i] / team_counts[i] / 100, 2)
        text += f"Average rating: {avg_score}_\n"

    chat_id = update.message.chat_id
    pending_teams[chat_id] = {
        "date": game_date,
        "teams": teams,
        "team_names": team_names,
        "sums": team_sums,
        "counts": team_counts
    }

    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_teams")],
        [InlineKeyboardButton("🔁 Regenerate", callback_data="regenerate_teams")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
