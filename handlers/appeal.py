from telegram import Update, Poll
from telegram.ext import CallbackContext
from handlers.poll_handler import scheduled_poll_finalize_job

from services.sheets import spreadsheet, appeals_sheet, get_existing_teams
from services.appeal_service import (
    can_create_appeal_today,
    get_today_teams_and_players,
    create_appeal_record,
    is_appeal_active
)
from utils.misc import get_today_date


def appeal(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command can only be used in a group.")
        return

    try:
        today = get_today_date()

        if not can_create_appeal_today(today):
            update.message.reply_text(
                "⚠️ An appeal has already been created today. You can only create one appeal per day.")
            return

        if is_appeal_active(today):
            update.message.reply_text("⚠️ An appeal is already active. Please wait for the current poll to finish.")
            return

        teams_data = get_today_teams_and_players(today)

        if not teams_data:
            update.message.reply_text("⚠️ No teams found for today.")
            return

        appeal_id = create_appeal_record(today, teams_data)

        polls_created = 0
        chat_id = update.message.chat_id

        for team_name, players in teams_data.items():
            if len(players) < 2:
                continue

            poll_players = players[:10]
            question = f"🏐 Who contributed the most in team {team_name}?"

            # Використовуємо звичайний poll без open_period
            poll_message = context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=poll_players,
                is_anonymous=True,
                allows_multiple_answers=True  # Змінено на False для кращої логіки
            )

            appeals_sheet.append_row([
                appeal_id,
                today,
                team_name,
                poll_message.poll.id,
                poll_message.message_id,
                chat_id,
                'active',
                ''
            ])

            polls_created += 1

            # Плануємо автоматичне завершення через 600 сек (10 хв)
            print(f"🕒 Scheduling poll {poll_message.poll.id} to close in 600 seconds")
            context.job_queue.run_once(
                scheduled_poll_finalize_job,
                when=60,  # 10 хвилин
                context={
                    'chat_id': chat_id,
                    'message_id': poll_message.message_id,
                    'poll_id': poll_message.poll.id
                },
                name=f"poll_close_{poll_message.poll.id}"
            )

        if polls_created == 0:
            update.message.reply_text(
                "⚠️ Poll creation failed. Please ensure each team has at least 2 players.")
            return

        success_message = f"✅ Appeal created! {polls_created} polls have been launched.\n\n"
        success_message += "📊 Conditions for awarding bonus points:\n"
        success_message += "• At least 6 votes in the poll\n"
        success_message += "• 66%+ votes for one player\n"
        success_message += "• bonus points for each match played today\n\n"
        success_message += "⏰ Voting will be open for 10 minutes."

        update.message.reply_text(success_message)

    except Exception as e:
        print(f"❌ Appeal command failed : {e}")
        update.message.reply_text(f"⚠️ An error occurred while creating the appeal: {e}")