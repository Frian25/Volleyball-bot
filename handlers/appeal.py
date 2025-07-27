from telegram import Update, Poll
from telegram.ext import CallbackContext
from datetime import datetime, timedelta

from services.sheets import spreadsheet, get_existing_teams
from services.appeal_service import (
    can_create_appeal_today,
    get_today_teams_and_players,
    create_appeal_record,
    is_appeal_active
)
from utils.misc import get_today_date


def appeal(update: Update, context: CallbackContext):
    """Команда для створення апеляції з анонімними голосуваннями"""

    # Перевіряємо, що команда викликана в груповому чаті
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command can only be used in a group.")
        return

    try:
        today = get_today_date()

        # Перевіряємо, чи вже була створена апеляція сьогодні
        if not can_create_appeal_today(today):
            update.message.reply_text(
                "⚠️ An appeal has already been created today. You can only create one appeal per day.")
            return

        # Перевіряємо, чи є активна апеляція
        if is_appeal_active(today):
            update.message.reply_text("⚠️ An appeal is already active. Please wait for the current poll to finish.")
            return

        # Отримуємо команди та гравців на сьогодні
        teams_data = get_today_teams_and_players(today)

        if not teams_data:
            update.message.reply_text(
                "⚠️ No teams found for today.")
            return

        # Створюємо запис про апеляцію
        appeal_id = create_appeal_record(today, teams_data)

        # Створюємо poll для кожної команди
        polls_created = []
        chat_id = update.message.chat_id

        for team_name, players in teams_data.items():
            if len(players) < 2:  # Пропускаємо команди з менше ніж 2 гравцями
                continue

            # Обмежуємо до 10 гравців (ліміт Telegram Poll)
            poll_players = players[:10]

            # Створюємо питання для poll
            question = f"🏐 Who contributed the most in team {team_name}?"

            # Створюємо poll
            poll_message = context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=poll_players,
                is_anonymous=True,
                allows_multiple_answers=True,  # Дозволяємо вибрати до 3 варіантів
                open_period=60,  # 10 хвилин = 600 секунд
                explanation="Pick up to 3 top players from this team today. At least 6 votes are needed to validate the results."
            )

            polls_created.append({
                'team': team_name,
                'poll_id': poll_message.poll.id,
                'message_id': poll_message.message_id
            })

        if not polls_created:
            update.message.reply_text(
                "⚠️ Poll creation failed. Please ensure each team has at least 2 players.")
            return

        # Зберігаємо інформацію про створені poll'и
        appeals_sheet = spreadsheet.worksheet("Appeals")
        for poll_info in polls_created:
            appeals_sheet.append_row([
                appeal_id,
                today,
                poll_info['team'],
                poll_info['poll_id'],
                poll_info['message_id'],
                'active',
                ''  # results (буде заповнено після завершення)
            ])

        success_message = f"✅ Appeal created! {len(polls_created)} polls have been launched.\n\n"
        success_message += "📊 Conditions for awarding bonus points:\n"
        success_message += "• At least 6 votes in the poll\n"
        success_message += "• 66%+ votes for one player\n"
        success_message += "• bonus points for each match played today\n\n"
        success_message += "⏰ Voting will be open for 10 minutes."

        update.message.reply_text(success_message)

    except Exception as e:
        print(f"❌ Appeal command failed : {e}")
        update.message.reply_text(f"⚠️ An error occurred while creating the appeal: {e}")