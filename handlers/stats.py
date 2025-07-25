from telegram import Update
from telegram.ext import CallbackContext

from services.rating_logic import (
    get_current_ratings,
    get_player_games_count,
    calculate_dynamic_k_factor,
    get_player_rating_history,
    create_rating_chart
)

from utils.misc import is_quota_exceeded_error


def stats(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("⚠️ Usage: /stats PlayerName")
        return

    if update.message.chat.type != 'private':
        update.message.reply_text("⚠️ Please use this command in a private chat.")
        return

    player_name = " ".join(context.args)
    current_ratings = get_current_ratings()

    if player_name not in current_ratings:
        update.message.reply_text(f"⚠️ Player '{player_name}' not found.")
        return

    current_rating = current_ratings[player_name]
    games_played = get_player_games_count(player_name)
    k_factor = calculate_dynamic_k_factor(games_played, current_rating)

    # Визначаємо статус гравця
    if games_played < 5:
        status = "🔥 Rookie (fast adaptation)"
    elif games_played < 15:
        status = "📈 Adapting"
    elif games_played < 25:
        status = "📊 Stabilizing"
    else:
        status = "✅ Stable"

    message = f"📊 Stats for: {player_name}\n"
    message += f"🏆 Rating: {current_rating}\n"
    message += f"🎮 Matches Played: {games_played}\n"
    message += f"⚡ K-factor: {k_factor}\n"
    message += f"📈 Status: {status}\n"

    if games_played < 25:
        remaining = 25 - games_played
        message += f"\n🧪 {remaining} more match(es) until full stabilization"

    update.message.reply_text(message)

    if games_played > 0:
        history = get_player_rating_history(player_name)
        if history:
            chart_buffer = create_rating_chart(player_name, history)
            if chart_buffer:
                update.message.reply_photo(
                    photo=chart_buffer,
                    caption=f"📈 Rating trend: {player_name}"
                )