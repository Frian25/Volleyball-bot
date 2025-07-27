from telegram import Update
from telegram.ext import CallbackContext

from services.appeal_service import process_poll_results


def poll_answer_handler(update: Update, context: CallbackContext):
    """Обробляє відповіді на голосування (не потрібно для анонімних poll'ів)"""
    # Для анонімних голосувань цей хендлер не спрацьовує
    pass


def poll_handler(update: Update, context: CallbackContext):
    """Обробляє оновлення голосувань, включаючи їх завершення"""

    poll = update.poll

    if not poll:
        return

    # Перевіряємо, чи голосування завершено
    if not poll.is_closed:
        return

    try:
        # Підраховуємо результати
        poll_results = {}
        total_voter_count = poll.total_voter_count

        for option in poll.options:
            poll_results[option.text] = option.voter_count

        # Обробляємо результати
        winner = process_poll_results(poll.id, poll_results)

        # Відправляємо повідомлення про результати
        chat_id = update.effective_chat.id

        if total_voter_count < 6:
            message = f"📊 Poll ended!\n\n"
            message += f"❌ Not enough votes to award bonus points.\n"
            message += f"Votes received: {total_voter_count}\n"
            message += f"Required minimum: 6\n\n"
            message += "📈 Poll results:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                message += f"• {option}: {votes} ({percentage:.1f}%)\n"

        elif winner:
            winner_votes = poll_results[winner]
            win_percentage = (winner_votes / total_voter_count) * 100

            message = f"📊 Poll ended!\n\n"
            message += f"🏆 MVP selected: **{winner}**\n"
            message += f"✅ Received {winner_votes} out of {total_voter_count} votes ({win_percentage:.1f}%)\n"
            message += f"🎉 Bonus points added for each match played today!\n\n"
            message += "📈 Full results:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                emoji = "🏆" if option == winner else "•"
                message += f"{emoji} {option}: {votes} ({percentage:.1f}%)\n"

        else:
            max_votes = max(poll_results.values()) if poll_results else 0
            max_percentage = (max_votes / total_voter_count * 100) if total_voter_count > 0 else 0

            message = f"📊 Poll ended!\n\n"
            message += f"❌ No player received enough votes (66%+ required).\n"
            message += f"Top vote count: {max_votes} ({max_percentage:.1f}%)\n"
            message += f"Total votes: {total_voter_count}\n\n"
            message += "📈 Poll results:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                message += f"• {option}: {votes} ({percentage:.1f}%)\n"

        context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )

    except Exception as e:
        print(f"❌ Error while processing finished poll: {e}")
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ An error occurred while processing the poll results.")