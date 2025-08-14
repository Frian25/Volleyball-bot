import time
from datetime import datetime, timedelta
from telegram import Update, Poll
from telegram.ext import CallbackContext

from services.sheets import spreadsheet, appeals_sheet, get_existing_teams
from services.appeal_service import (
    can_create_appeal_today,
    get_today_teams_and_players,
    create_appeal_record,
    is_appeal_active,
    process_poll_results
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

        # Створюємо polls і зберігаємо інформацію для автоматичного закриття
        poll_jobs = []

        for team_name, players in teams_data.items():
            if len(players) < 2:
                continue

            poll_players = players[:10]
            question = f"🏐 Who contributed the most in team {team_name}?"

            # Створюємо poll БЕЗ open_period (будемо закривати вручну)
            poll_message = context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=poll_players,
                is_anonymous=True,
                allows_multiple_answers=True
            )

            # Зберігаємо інформацію про poll
            close_time = datetime.now() + timedelta(minutes=10)  # 10 хвилин
            appeals_sheet.append_row([
                appeal_id,
                today,
                team_name,
                poll_message.poll.id,
                poll_message.message_id,
                chat_id,
                'active',
                close_time.strftime("%Y-%m-%d %H:%M:%S")
            ])

            # Створюємо індивідуальну job для кожного poll
            job_name = f"close_poll_{poll_message.poll.id}"

            context.job_queue.run_once(
                close_single_poll,
                when=600,  # 10 хвилин в секундах
                context={
                    'chat_id': chat_id,
                    'poll_id': poll_message.poll.id,
                    'message_id': poll_message.message_id,
                    'team_name': team_name,
                    'appeal_id': appeal_id
                },
                name=job_name
            )

            polls_created += 1
            print(f"✅ Created poll {poll_message.poll.id} for team {team_name}, will close at {close_time}")

        if polls_created == 0:
            update.message.reply_text(
                "⚠️ Poll creation failed. Please ensure each team has at least 2 players.")
            return

        success_message = f"✅ Appeal created! {polls_created} polls have been launched.\n\n"
        success_message += "📊 Conditions for awarding bonus points:\n"
        success_message += "• At least 6 votes in the poll\n"
        success_message += "• 66%+ votes for one player\n"
        success_message += "• Bonus points for each match played today\n\n"
        success_message += "⏰ Voting will be open for 10 minutes."

        update.message.reply_text(success_message)

    except Exception as e:
        print(f"❌ Appeal command failed: {e}")
        update.message.reply_text(f"⚠️ An error occurred while creating the appeal: {e}")


def close_single_poll(context: CallbackContext):
    """Закриває один конкретний poll після завершення часу"""
    job_data = context.job.context
    chat_id = job_data['chat_id']
    poll_id = job_data['poll_id']
    message_id = job_data['message_id']
    team_name = job_data['team_name']
    appeal_id = job_data['appeal_id']

    print(f"🛑 Attempting to close poll {poll_id} for team {team_name}")

    try:
        # Закриваємо poll
        poll = context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
        print(f"✅ Poll {poll_id} closed successfully")

        # Обробляємо результати
        poll_results = {opt.text: opt.voter_count for opt in poll.options}
        winner = process_poll_results(poll_id, poll_results)

        # Оновлюємо статус в таблиці Appeals
        update_poll_status_in_sheet(poll_id, 'completed')

        # Відправляємо результати в чат
        send_poll_results(context, chat_id, team_name, poll_results, winner, poll.total_voter_count)

        print(f"🎉 Poll {poll_id} processed successfully")

    except Exception as e:
        error_msg = str(e)
        if "Poll has already been closed" in error_msg:
            print(f"⚠️ Poll {poll_id} was already closed")
            # Все одно оновлюємо статус
            update_poll_status_in_sheet(poll_id, 'completed')
        else:
            print(f"❌ Failed to close poll {poll_id}: {e}")
            # Відправляємо повідомлення про помилку
            try:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Error processing poll for team {team_name}: {error_msg}"
                )
            except:
                pass


def update_poll_status_in_sheet(poll_id, new_status):
    """Оновлює статус poll в таблиці Appeals"""
    try:
        all_rows = appeals_sheet.get_all_values()
        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) >= 4 and row[3] == poll_id:  # poll_id в 4-й колонці (індекс 3)
                appeals_sheet.update_cell(i, 7, new_status)  # status в 7-й колонці
                print(f"✅ Updated poll {poll_id} status to {new_status}")
                return
        print(f"⚠️ Poll {poll_id} not found in Appeals sheet")
    except Exception as e:
        print(f"❌ Error updating poll status: {e}")


def send_poll_results(context, chat_id, team_name, poll_results, winner, total_voter_count):
    """Відправляє результати poll'у в чат"""
    try:
        if total_voter_count < 6:
            message = f"📊 Poll ended for team {team_name}!\n\n"
            message += f"❌ Not enough votes to award bonus points.\n"
            message += f"Votes received: {total_voter_count}\n"
            message += f"Required minimum: 6\n\n"
        elif winner:
            winner_votes = poll_results[winner]
            win_percentage = (winner_votes / total_voter_count) * 100
            message = f"📊 Poll ended for team {team_name}!\n\n"
            message += f"🏆 MVP selected: **{winner}**\n"
            message += f"✅ Received {winner_votes} out of {total_voter_count} votes ({win_percentage:.1f}%)\n"
            message += f"🎉 Bonus points added for each match played today!\n\n"
        else:
            max_votes = max(poll_results.values()) if poll_results else 0
            max_percentage = (max_votes / total_voter_count * 100) if total_voter_count > 0 else 0
            message = f"📊 Poll ended for team {team_name}!\n\n"
            message += f"❌ No player received enough votes (66%+ required).\n"
            message += f"Top vote count: {max_votes} ({max_percentage:.1f}%)\n\n"

        message += "📈 Results:\n"
        for option, votes in sorted(poll_results.items(), key=lambda x: x[1], reverse=True):
            percentage = (votes / total_voter_count * 100) if total_voter_count > 0 else 0
            emoji = "🏆" if winner and option == winner else "•"
            message += f"{emoji} {option}: {votes} ({percentage:.1f}%)\n"

        context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        print(f"📤 Results sent for team {team_name}")

    except Exception as e:
        print(f"❌ Error sending poll results: {e}")


def check_polls_manual(update: Update, context: CallbackContext):
    """Ручна перевірка та закриття прострочених polls"""
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command can only be used in a group.")
        return

    try:
        chat_id = update.message.chat_id
        current_time = datetime.now()
        print(f"🧪 Manual poll check at {current_time}")

        all_rows = appeals_sheet.get_all_values()
        if len(all_rows) <= 1:
            update.message.reply_text("ℹ️ No polls found.")
            return

        headers = all_rows[0]
        closed_polls = 0

        # Створюємо індекс колонок
        col_idx = {}
        for idx, header in enumerate(headers):
            col_idx[header.strip().lower()] = idx

        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) < 8:
                continue

            try:
                status = row[col_idx.get('status', 6)].strip()
                row_chat_id = int(row[col_idx.get('chat_id', 5)])
                poll_id = row[col_idx.get('poll_id', 3)].strip()
                message_id = int(row[col_idx.get('message_id', 4)])
                team_name = row[col_idx.get('team_name', 2)].strip()
                end_time_str = row[col_idx.get('end_time', 7)].strip()

                if status != "active" or row_chat_id != chat_id:
                    continue

                try:
                    end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    print(f"⚠️ Invalid date format: {end_time_str}")
                    continue

                if current_time >= end_time:
                    print(f"🕐 Poll {poll_id} expired, closing manually")

                    try:
                        poll = context.bot.stop_poll(chat_id=chat_id, message_id=message_id)

                        poll_results = {opt.text: opt.voter_count for opt in poll.options}
                        winner = process_poll_results(poll_id, poll_results)

                        # Оновлюємо статус
                        appeals_sheet.update_cell(i, col_idx.get('status', 6) + 1, 'completed')

                        send_poll_results(context, chat_id, team_name, poll_results, winner, poll.total_voter_count)

                        closed_polls += 1
                        print(f"✅ Manually closed poll {poll_id}")

                    except Exception as poll_error:
                        if "Poll has already been closed" in str(poll_error):
                            appeals_sheet.update_cell(i, col_idx.get('status', 6) + 1, 'completed')
                            print(f"⚠️ Poll {poll_id} already closed")
                        else:
                            print(f"❌ Error closing poll {poll_id}: {poll_error}")

            except Exception as row_error:
                print(f"⚠️ Error processing row {i}: {row_error}")

        if closed_polls > 0:
            update.message.reply_text(f"✅ Manually closed {closed_polls} expired polls.")
        else:
            update.message.reply_text("ℹ️ No expired polls found.")

    except Exception as e:
        print(f"❌ Error in manual poll check: {e}")
        update.message.reply_text(f"⚠️ Error checking polls: {e}")


# Функція для очищення старих jobs (додаткова безпека)
def cleanup_old_jobs(context: CallbackContext):
    """Очищує старі завершені jobs"""
    try:
        current_jobs = context.job_queue.jobs()
        removed_count = 0

        for job in current_jobs:
            if job.name and job.name.startswith('close_poll_'):
                # Перевіряємо чи job не застряг
                if hasattr(job, 'next_t') and job.next_t and job.next_t < time.time() - 3600:  # старші 1 години
                    job.schedule_removal()
                    removed_count += 1

        if removed_count > 0:
            print(f"🧹 Cleaned up {removed_count} old poll jobs")

    except Exception as e:
        print(f"⚠️ Error during job cleanup: {e}")