from telegram import Update
from telegram.ext import CallbackContext

from services.appeal_service import process_poll_results
from services.sheets import  appeals_sheet
import time


def poll_answer_handler(update: Update, context: CallbackContext):
    """Обробляє відповіді на голосування (не потрібно для анонімних poll'ів)"""
    # Для анонімних голосувань цей хендлер не спрацьовує
    pass

def get_chat_id_by_poll_id(poll_id):
    try:
        all_rows = appeals_sheet.get_all_values()

        for row in all_rows[1:]:
            if len(row) >= 6 and row[3] == poll_id:
                return int(row[5])  # chat_id — колонка 6
        return None
    except Exception as e:
        print(f"Error while getting chat_id: {e}")
        return None

def poll_handler(update: Update, context: CallbackContext):
    """Обробляє оновлення голосувань, включаючи їх завершення"""
    print("✅ Poll update received!")
    poll = update.poll
    print(f"🗳 Poll ID: {poll.id}, closed: {poll.is_closed}, total votes: {poll.total_voter_count}")

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

        chat_id = get_chat_id_by_poll_id(poll.id)
        if not chat_id:
            print("⚠️ Chat ID not found for poll.")
            return

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

def scheduled_poll_finalize_job(context: CallbackContext):
    """Завершує poll через JobQueue і обробляє результати"""
    job_data = context.job.context
    chat_id = job_data['chat_id']
    message_id = job_data['message_id']
    poll_id = job_data['poll_id']

    try:
        poll = context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
        print(f"🛑 Poll {poll_id} stopped automatically via JobQueue")

        poll_results = {opt.text: opt.voter_count for opt in poll.options}
        winner = process_poll_results(poll.id, poll_results)

        print(f"✅ Poll {poll_id} processed. Winner: {winner}")

    except Exception as e:
        print(f"❌ Failed to process poll {poll_id}: {e}")