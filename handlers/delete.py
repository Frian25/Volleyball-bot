from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime

from services.sheets import match_sheet, rating_sheet
from utils.misc import get_today_date, is_quota_exceeded_error


def delete(update: Update, context: CallbackContext):
    if update.message.chat.type == 'private':
        update.message.reply_text("⚠️ This command is for group chats only.")
        return

    try:
        all_rows = match_sheet.get_all_values()
        if len(all_rows) <= 1:
            update.message.reply_text("⚠️ No data found in match sheet.")
            return

        headers = all_rows[0]
        data_rows = all_rows[1:]

        today = get_today_date()
        date_index = headers.index("date") if "date" in headers else 1

        # Знаходимо всі рядки за сьогодні
        deletable_indices = []
        for i, row in enumerate(data_rows):
            if len(row) > date_index and row[date_index] == today:
                deletable_indices.append(i + 2)  # +2 бо заголовок + зсув

        if not deletable_indices:
            update.message.reply_text("⚠️ No matches today to delete.")
            return

        last_row_index = deletable_indices[-1]
        deleted_row = all_rows[last_row_index - 1]
        match_id_to_delete = deleted_row[0] if deleted_row else None

        match_sheet.delete_rows(last_row_index)

        # Видаляємо пов'язаний запис у Rating
        rating_rows = rating_sheet.get_all_values()
        for i, row in enumerate(rating_rows[1:], start=2):  # Пропускаємо заголовок
            if row and row[0] == match_id_to_delete:
                rating_sheet.delete_rows(i)
                break

        update.message.reply_text("✅ Last match has been deleted.")

    except Exception as e:
        if is_quota_exceeded_error(e):
            update.message.reply_text("❌ Google Sheets quota exceeded. Try again later.")
        else:
            update.message.reply_text(f"⚠️ Error while deleting: {e}")