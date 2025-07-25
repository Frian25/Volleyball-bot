from telegram import Update
from telegram.ext import CallbackContext

from services.rating_logic import get_current_ratings, get_player_games_count
from utils.misc import is_quota_exceeded_error


def leaderboard(update: Update, context: CallbackContext):
    try:
        current_ratings = get_current_ratings()

        if not current_ratings:
            update.message.reply_text("⚠️ No rating data available.")
            return

        sorted_players = sorted(current_ratings.items(), key=lambda x: x[1], reverse=True)

        message = "🏆 Top Players:\n\n"
        for i, (player, rating) in enumerate(sorted_players[:10], 1):
            games = get_player_games_count(player)
            if i == 1:
                message += f"🥇 {player}: {rating} ({games} sets)\n"
            elif i == 2:
                message += f"🥈 {player}: {rating} ({games} sets)\n"
            elif i == 3:
                message += f"🥉 {player}: {rating} ({games} sets)\n"
            else:
                message += f"{i}. {player}: {rating} ({games} sets)\n"

        update.message.reply_text(message)

    except Exception as e:
        if is_quota_exceeded_error(e):
            update.message.reply_text("❌ Google Sheets quota exceeded. Try again shortly.")
        else:
            update.message.reply_text(f"⚠️ Error: {e}")
