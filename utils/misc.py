import time
from datetime import datetime


def is_quota_exceeded_error(e):
    """
    Перевіряє, чи виняток викликаний перевищенням ліміту Google API
    """
    error_str = str(e).lower()
    return any(keyword in error_str for keyword in [
        "quota exceeded", "resource_exhausted", "rate limit",
        "too many requests", "service unavailable"
    ])


def get_today_date():
    """Повертає поточну дату у форматі YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_timestamp():
    """Поточний timestamp (для health endpoint)"""
    return time.time()
