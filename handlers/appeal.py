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

        for team_name, players in teams_data.items():
            if len(players) < 2:
                continue

            poll_players = players[:10]
            question = f"🏐 Who contributed the most in team {team_name}?"
            closer = 600
            # Створюємо poll БЕЗ open_period
            poll_message = context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=poll_players,
                open_period=closer,
                is_anonymous=True,
                allows_multiple_answers=True
            )

            # Зберігаємо інформацію про poll з timestamp закриття
            close_time = datetime.now() + timedelta(seconds=closer)  # 10 хвилин
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

            polls_created += 1
            print(f"✅ Created poll {poll_message.poll.id} for team {team_name}, scheduled to close at {close_time}")

        if polls_created == 0:
            update.message.reply_text(
                "⚠️ Poll creation failed. Please ensure each team has at least 2 players.")
            return

        # Запускаємо job для періодичної перевірки poll'ів (кожні 30 секунд)
        context.job_queue.run_repeating(
            check_and_close_polls,
            interval=30,  # кожні 30 секунд
            first=30,  # перша перевірка через 30 секунд
            context={'chat_id': chat_id, 'appeal_id': appeal_id},
            name=f"poll_checker_{appeal_id}"
        )

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


def check_and_close_polls(context: CallbackContext):
    """Job функція, яка періодично перевіряє та закриває прострочені poll'и"""
    job_data = context.job.context
    chat_id = job_data['chat_id']
    appeal_id = job_data['appeal_id']

    print(f"🔍 Checking polls for appeal {appeal_id}")

    try:
        current_time = datetime.now()

        # Отримуємо всі активні poll'и для цього appeal'у
        all_rows = appeals_sheet.get_all_values()
        polls_to_close = []
        active_polls_count = 0

        for i, row in enumerate(all_rows[1:], start=2):
            if (len(row) >= 8 and
                    row[0] == appeal_id and  # appeal_id
                    row[6] == 'active' and  # status
                    int(row[5]) == chat_id):  # chat_id

                active_polls_count += 1
                poll_id = row[3]
                message_id = int(row[4])
                close_time_str = row[7]
                team_name = row[2]

                try:
                    close_time = datetime.strptime(close_time_str, "%Y-%m-%d %H:%M:%S")

                    # Якщо час закриття пройшов
                    if current_time >= close_time:
                        polls_to_close.append({
                            'row_index': i,
                            'poll_id': poll_id,
                            'message_id': message_id,
                            'team_name': team_name
                        })

                except ValueError as e:
                    print(f"⚠️ Invalid date format in row {i}: {close_time_str}")

        # Закриваємо прострочені poll'и
        for poll_info in polls_to_close:
            try:
                print(f"🛑 Closing poll {poll_info['poll_id']} for team {poll_info['team_name']}")

                # Закриваємо poll
                poll = context.bot.stop_poll(chat_id=chat_id, message_id=poll_info['message_id'])

                # Обробляємо результати
                poll_results = {opt.text: opt.voter_count for opt in poll.options}
                winner = process_poll_results(poll_info['poll_id'], poll_results)

                # Оновлюємо статус в таблиці
                appeals_sheet.update_cell(poll_info['row_index'], 7, 'completed')

                # Відправляємо результати
                send_poll_results(context, chat_id, poll_info['team_name'], poll_results, winner,
                                  poll.total_voter_count)

                print(f"✅ Successfully processed poll {poll_info['poll_id']}")

            except Exception as poll_error:
                print(f"❌ Failed to close poll {poll_info['poll_id']}: {poll_error}")

        # Якщо всі poll'и закрито, зупиняємо job
        remaining_active = active_polls_count - len(polls_to_close)
        if remaining_active == 0:
            print(f"🏁 All polls for appeal {appeal_id} processed. Stopping job.")
            context.job.schedule_removal()
        else:
            print(f"⏳ {remaining_active} polls still active for appeal {appeal_id}")

    except Exception as e:
        print(f"❌ Error in check_and_close_polls: {e}")


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

    except Exception as e:
        print(f"❌ Error sending poll results: {e}")


def check_polls_manual(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command can only be used in a group.")
        return

    try:
        chat_id = update.message.chat_id
        current_time = datetime.now()
        print(f"🧪 Checking polls manually at {current_time}")

        all_rows = appeals_sheet.get_all_values()
        headers = all_rows[0]
        data = all_rows[1:]
        closed_polls = 0

        col_idx = {key.strip(): idx for idx, key in enumerate(headers)}  # strip пробіли!

        for i, row in enumerate(data, start=2):
            try:
                status = row[col_idx["status"]].strip()
                row_chat_id = int(row[col_idx["chat_id"]])
                poll_id = row[col_idx["poll_id"]].strip()
                message_id = int(row[col_idx["message_id"]])
                team_name = row[col_idx["team_name"]].strip()
                close_time_str = row[col_idx["end_time"]].strip()

                print(f"🔎 Row {i} → status={status}, chat_id={row_chat_id}, poll_id={poll_id}, end={close_time_str}")

                if status != "active" or row_chat_id != chat_id:
                    continue

                try:
                    close_time = datetime.strptime(close_time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    print(f"⚠️ Could not parse close_time: {close_time_str} → {e}")
                    continue

                if current_time >= close_time:
                    print(f"✅ Poll {poll_id} is expired (now: {current_time}, close: {close_time})")

                    try:
                        poll = context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
                    except Exception as stop_err:
                        if "Poll has already been closed" in str(stop_err):
                            print(f"⚠️ Poll {poll_id} already closed, skipping stop_poll")
                            appeals_sheet.update_cell(i, col_idx["status"] + 1, 'completed')
                            continue
                        else:
                            raise stop_err

                    poll_results = {opt.text: opt.voter_count for opt in poll.options}
                    winner = process_poll_results(poll_id, poll_results)

                    appeals_sheet.update_cell(i, col_idx["status"] + 1, 'completed')
                    send_poll_results(context, chat_id, team_name, poll_results, winner, poll.total_voter_count)

                    closed_polls += 1
                    print(f"🛑 Manually closed poll {poll_id}")

            except Exception as row_err:
                print(f"⚠️ Failed to process row {i}: {row_err}")

        if closed_polls > 0:
            update.message.reply_text(f"✅ Manually processed {closed_polls} expired polls.")
        else:
            update.message.reply_text("ℹ️ No expired polls found to close.")

    except Exception as e:
        print(f"❌ Error in manual poll check: {e}")
        update.message.reply_text(f"⚠️ Error checking polls: {e}")