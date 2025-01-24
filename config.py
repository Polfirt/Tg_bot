# config.py
# Файл конфигурации бота.
import os
from dotenv import load_dotenv

load_dotenv()

# Получение токена бота из переменных окружения (.env файл).
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка наличия BOT_TOKEN в переменных окружения.
if not BOT_TOKEN:
    exit("Error: BOT_TOKEN is not set in .env file")