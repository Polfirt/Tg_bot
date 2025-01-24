# utils.py
# Файл с утилитарными функциями, в данном случае для определения часового пояса по геолокации.
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from geopy.exc import GeocoderTimedOut # Импорт исключения для обработки timeout.
import logging

# utils.py

async def get_timezone_from_location(latitude: float, longitude: float) -> str | None:
    """
    Асинхронная функция для определения часового пояса по координатам широты и долготы.
    Использует сервисы geopy и timezonefinder.
    """
    geolocator = Nominatim(user_agent="medicine_reminder_bot", timeout=10) # Инициализация geolocator с user_agent и timeout.
    tf = TimezoneFinder() # Инициализация TimezoneFinder для поиска часового пояса.
    try:
        location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=10) # Получение обратного геокодирования с timeout.
        if location:
            timezone = tf.timezone_at(lng=longitude, lat=latitude) # Определение часового пояса по координатам.
            return timezone # Возвращает название часового пояса, например "Europe/Moscow".
    except GeocoderTimedOut:
        raise GeocoderTimedOut("Service timed out") # Проброс исключения GeocoderTimedOut для обработки в handlers.py.
    except Exception as e:
        logging.error(f"Geocoder error: {e}") # Логирование ошибок geocoder.
        return None # Возвращает None в случае ошибки.
    return None # Возвращает None, если не удалось определить часовой пояс.