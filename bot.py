# bot.py
# Главный файл бота, запускает бота и планировщик задач.
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from datetime import datetime, timedelta, time
import pytz
from config import BOT_TOKEN
from handlers import router
from database import create_tables, get_all_medicines_with_time, get_user_timezone, decrement_medicine_quantity, get_medicine_by_id, delete_medicine

# bot.py
# aiogram: 3.x.x
# python: 3.9+

logging.basicConfig(level=logging.INFO)

async def set_commands(bot: Bot):
    """
    Установка списка команд бота, отображаемых в меню.
    """
    commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
        BotCommand(command="/add", description="Добавить лекарство 💊"),
        BotCommand(command="/status", description="Показать список лекарств 📋"),
        BotCommand(command="/delete", description="Удалить лекарство 🗑️"),
        BotCommand(command="/timezone", description="Изменить часовой пояс 🌍")
    ]
    await bot.set_my_commands(commands)

async def send_reminder(bot: Bot, user_id: int, medicine_id: int, medicine_name: str, medicine_dosage: str, medicine_dosage_unit: str): # Добавили medicine_dosage_unit
    """
    Отправка напоминания пользователю о приеме лекарства.
    Уменьшает количество оставшихся доз в базе данных и удаляет лекарство, если оно закончилось.
    """
    logging.info(f"Отправка напоминания пользователю {user_id}: {medicine_name} (доза: {medicine_dosage} {medicine_dosage_unit})")
    try:
        dosage_str = medicine_dosage.rstrip('0').rstrip('.') if '.' in medicine_dosage else medicine_dosage # Убираем лишние нули и точку из дробной части для красивого отображения дозировки.
        dosage_value = float(medicine_dosage)

        unit_text = medicine_dosage_unit
        reminder_message = f"⏰ Напоминание! Примите {dosage_str} {unit_text} {medicine_name} 💊"
        await bot.send_message(user_id, reminder_message)
        logging.info(f"Напоминание успешно отправлено пользователю {user_id}")
        medicine_info = await get_medicine_by_id(medicine_id) # Получение информации о лекарстве из базы данных.
        if medicine_info:
            current_remaining_quantity = medicine_info[5] # remaining_quantity - 6й элемент в кортеже (после добавления dosage_unit)
            if current_remaining_quantity > 0:
                dosage_val = 1 # Доза по умолчанию для уменьшения остатка (если не удастся распарсить дозировку, хотя теперь дозировка - число).
                try:
                    dosage_val = float(medicine_dosage) # Попытка преобразования дозировки в число.
                except ValueError:
                    logging.warning(f"Не удалось распарсить дозировку '{medicine_dosage}' для medicine_id {medicine_id}, используем дозу по умолчанию 1 для уменьшения остатка.")

                await decrement_medicine_quantity(medicine_id, dosage_val) # Уменьшение оставшегося количества лекарства в БД.
                updated_medicine_info = await get_medicine_by_id(medicine_id) # Получение обновленной информации о лекарстве.
                if updated_medicine_info and updated_medicine_info[5] <= 0: # Проверка, что лекарство закончилось.
                    await bot.send_message(user_id, f"💊 Внимание! Лекарство '{medicine_name}' закончилось. Пожалуйста, пополните запасы. ⏳")
                    await delete_medicine(medicine_id) # Автоматическое удаление лекарства из базы данных.
            elif current_remaining_quantity <= 0:
                logging.info(f"Лекарство {medicine_name} (medicine_id {medicine_id}) уже закончилось или остаток <= 0, напоминание не приведет к уменьшению остатка.")

    except Exception as e:
        logging.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")

async def scheduler_setup(bot: Bot):
    """
    Настройка и запуск планировщика задач для отправки напоминаний.
    Проверяет базу данных каждую минуту на наличие напоминаний, которые нужно отправить.
    """
    logging.info("Запуск фоновой задачи проверки напоминаний каждую минуту")
    while True:
        now_utc = datetime.now(pytz.utc) # Текущее время в UTC.
        medicines = await get_all_medicines_with_time() # Получение всех лекарств с временем приема из базы данных.
        logging.info(f"Проверка напоминаний на {now_utc.strftime('%H:%M UTC')}. Найдено лекарств для проверки: {len(medicines)}")

        for medicine_id, user_id, name, dosage_str, dosage_unit, reminder_time_str, remaining_quantity in medicines: # Получаем dosage_unit и remaining_quantity из базы
            user_timezone_str = await get_user_timezone(user_id) # Получение часового пояса пользователя из базы данных.
            if user_timezone_str:
                user_timezone = pytz.timezone(user_timezone_str) # Преобразование часового пояса из строки в объект pytz.
                reminder_times = [datetime.strptime(rt.strip(), "%H:%M").time() for rt in reminder_time_str.split(',')] # Разделение и преобразование времени приема из строки в объекты time.
                dosages = [d.strip() for d in dosage_str.split(',')] # Разделение дозировок.
                now_user_tz = now_utc.astimezone(user_timezone) # Текущее время в часовом поясе пользователя.

                for index, reminder_time in enumerate(reminder_times): # Итерация по времени приема лекарства.
                    if now_user_tz.hour == reminder_time.hour and now_user_tz.minute == reminder_time.minute: # Проверка, совпадает ли текущее время с временем приема.
                        dose_to_send = dosages[index] if index < len(dosages) else dosages[-1] if dosages else "не указана" # Выбор дозировки для отправки в напоминании.
                        logging.info(f"Время отправлять напоминание для пользователя {user_id}, лекарство {name}, время {reminder_time.strftime('%H:%M')}, доза {dose_to_send} {dosage_unit}")
                        await send_reminder(bot, user_id, medicine_id, name, dose_to_send, dosage_unit) # Отправка напоминания, передаем dosage_unit
            else:
                logging.warning(f"Не удалось получить часовой пояс для пользователя {user_id}, напоминание для лекарства {name} не будет отправлено в этот раз.")

        await asyncio.sleep(60) # Пауза в 60 секунд перед следующей проверкой.

async def main():
    """
    Главная функция запуска бота.
    Инициализирует бота, диспетчер, устанавливает команды и запускает планировщик.
    """
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML) # Инициализация бота с использованием токена и режима HTML парсинга.
    dp = Dispatcher() # Инициализация диспетчера.
    dp.include_router(router) # Включение роутера обработчиков.

    await set_commands(bot) # Установка команд бота.
    await create_tables() # Создание таблиц в базе данных, если их нет.
    asyncio.create_task(scheduler_setup(bot)) # Запуск планировщика задач в фоновом режиме.

    await dp.start_polling(bot) # Запуск поллинга для приема обновлений от Telegram.

if __name__ == "__main__":
    asyncio.run(main())