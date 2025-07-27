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
            message = f"📊 Голосування завершено!\n\n"
            message += f"❌ Недостатньо голосів для нарахування бонусів.\n"
            message += f"Отримано голосів: {total_voter_count}\n"
            message += f"Потрібно мінімум: 6\n\n"
            message += "📈 Результати голосування:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                message += f"• {option}: {votes} ({percentage:.1f}%)\n"

        elif winner:
            # Розраховуємо відсоток голосів переможця
            winner_votes = poll_results[winner]
            win_percentage = (winner_votes / total_voter_count) * 100

            message = f"📊 Голосування завершено!\n\n"
            message += f"🏆 MVP обрано: **{winner}**\n"
            message += f"✅ Отримано {winner_votes} з {total_voter_count} голосів ({win_percentage:.1f}%)\n"
            message += f"🎉 Нарахованo +5 балів за кожен матч сьогодні!\n\n"
            message += "📈 Повні результати:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                emoji = "🏆" if option == winner else "•"
                message += f"{emoji} {option}: {votes} ({percentage:.1f}%)\n"

        else:
            # Жоден гравець не набрав 66%
            max_votes = max(poll_results.values()) if poll_results else 0
            max_percentage = (max_votes / total_voter_count * 100) if total_voter_count > 0 else 0

            message = f"📊 Голосування завершено!\n\n"
            message += f"❌ Жоден гравець не набрав достатньо голосів (потрібно 66%+).\n"
            message += f"Найбільше голосів: {max_votes} ({max_percentage:.1f}%)\n"
            message += f"Загальна кількість голосів: {total_voter_count}\n\n"
            message += "📈 Результати голосування:\n"
            for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
                percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
                message += f"• {option}: {votes} ({percentage:.1f}%)\n"

        context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )

    except Exception as e:
        print(f"❌ Помилка при обробці завершеного голосування: {e}")
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Сталася помилка при обробці результатів голосування."
        )