import os
import json

# Змінні середовища
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CREDS_JSON = json.loads(os.environ.get("CREDS_JSON", "{}"))
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

# Webhook
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{RENDER_HOST}/{BOT_TOKEN}" if RENDER_HOST else None

# Google Sheets URL (опціонально, можна передати як env)
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL", "https://docs.google.com/spreadsheets/d/1caXAMQ-xYbBt-8W6pMVOM99vaxabgSeDwIhp1Wsh6Dg/edit#gid=0")

# Рейтингова система
INITIAL_RATING = 1500
MAX_K_FACTOR = 50
MIN_K_FACTOR = 15
STABILIZATION_GAMES = 25
HIGH_RATING_THRESHOLD = 1700
HIGH_RATING_K_MULTIPLIER = 0.8
PLAYER_IMBALANCE_FACTOR = 50

# Непарні пари
INCOMPATIBLE_PAIRS = [
    ("Ігор Гончаренко", "Максим Лепський"),
    ("Богдан Бурко", "Максим Лепський"),
    ("Данило Шипрук", "Максим Лепський"),
    ("Єгор Верзун", "Максим Лепський"),
    ("Єгор Верзун", "Максим Вірченко"),
    ("Богдан Бурко", "Аліна Середа")
]
