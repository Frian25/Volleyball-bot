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
        update.message.reply_text("⚠️ Ця команда доступна тільки в груповому чаті.")
        return

    try:
        today = get_today_date()

        # Перевіряємо, чи вже була створена апеляція сьогодні
        if not can_create_appeal_today(today):
            update.message.reply_text(
                "⚠️ Апеляція вже була створена сьогодні. Можна створювати тільки одну апеляцію на день.")
            return

        # Перевіряємо, чи є активна апеляція
        if is_appeal_active(today):
            update.message.reply_text("⚠️ Апеляція вже активна. Дочекайтеся завершення поточного голосування.")
            return

        # Отримуємо команди та гравців на сьогодні
        teams_data = get_today_teams_and_players(today)

        if not teams_data:
            update.message.reply_text(
                "⚠️ Не знайдено команд на сьогодні. Спочатку потрібно створити команди за допомогою /generate_teams.")
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
            question = f"🏐 Хто найкраще зіграв у команді {team_name}?"

            # Створюємо poll
            poll_message = context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=poll_players,
                is_anonymous=True,
                allows_multiple_answers=True,  # Дозволяємо вибрати до 3 варіантів
                open_period=3600,  # 1 година = 3600 секунд
                explanation="Виберіть до 3 гравців, які найкраще зіграли в цій команді сьогодні. Мінімум 6 голосів для валідації."
            )

            polls_created.append({
                'team': team_name,
                'poll_id': poll_message.poll.id,
                'message_id': poll_message.message_id
            })

        if not polls_created:
            update.message.reply_text(
                "⚠️ Не вдалося створити голосування. Переконайтеся, що є команди з принаймні 2 гравцями.")
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

        success_message = f"✅ Апеляція створена! Створено {len(polls_created)} голосувань.\n\n"
        success_message += "📊 Умови для нарахування бонусних балів:\n"
        success_message += "• Мінімум 6 голосів у опитуванні\n"
        success_message += "• 66%+ голосів за одного гравця\n"
        success_message += "• +5 балів до рейтингу за кожен матч сьогодні\n\n"
        success_message += "⏰ Голосування триватиме 1 годину."

        update.message.reply_text(success_message)

    except Exception as e:
        print(f"❌ Помилка в команді appeal: {e}")
        update.message.reply_text(f"⚠️ Сталася помилка при створенні апеляції: {e}")