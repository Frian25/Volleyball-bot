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

        # 📉 Фільтруємо тільки тих, хто зіграв 15+ матчів
        eligible_players = []
        for player, rating in current_ratings.items():
            games = get_player_games_count(player)
            if games >= 15:
                eligible_players.append((player, rating, games))

        if not eligible_players:
            update.message.reply_text("⚠️ No players with 15 or more matches.")
            return

        # 🔝 Сортуємо за рейтингом
        sorted_players = sorted(eligible_players, key=lambda x: x[1], reverse=True)

        message = "🏆 Top Players (15+ matches):\n\n"
        for i, (player, rating, games) in enumerate(sorted_players[:10], 1):
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
