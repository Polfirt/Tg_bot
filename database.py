# database.py
# Файл для работы с базой данных SQLite.
import aiosqlite
from typing import List, Tuple

# database.py

DATABASE_NAME = "medicine_bot.db" # Имя файла базы данных.

async def create_tables():
    """
    Создание таблиц 'users' и 'medicines' в базе данных, если они не существуют.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db: # Асинхронное подключение к базе данных.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT
            )
        """) # SQL запрос для создания таблицы 'users' для хранения часовых поясов пользователей.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                dosage TEXT,
                dosage_unit TEXT,  -- Добавлено поле для единицы измерения дозировки
                doses_quantity INTEGER,
                reminder_time TEXT,
                remaining_quantity INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """) # SQL запрос для создания таблицы 'medicines' для хранения информации о лекарствах.
        await db.commit() # Применение изменений к базе данных.

async def get_user_timezone(user_id: int) -> str | None:
    """
    Получение часового пояса пользователя из базы данных по user_id.
    Возвращает часовой пояс в виде строки или None, если часовой пояс не установлен.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,)) as cursor: # SQL запрос для получения часового пояса.
            result = await cursor.fetchone()
            return result[0] if result else None # Возвращает часовой пояс или None.

async def set_user_timezone(user_id: int, timezone: str):
    """
    Установка или обновление часового пояса пользователя в базе данных.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, timezone) VALUES (?, ?)", (user_id, timezone)) # SQL запрос для добавления или обновления часового пояса.
        await db.commit() # Применение изменений к базе данных.

async def add_medicine(user_id: int, name: str, dosage: str, dosage_unit: str, doses_quantity: int, reminder_time: str): # Добавлен dosage_unit
    """
    Добавление нового лекарства в базу данных.
    Изначальное количество оставшихся доз устанавливается равным общему количеству доз в упаковке.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO medicines (user_id, name, dosage, dosage_unit, doses_quantity, reminder_time, remaining_quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, dosage, dosage_unit, doses_quantity, reminder_time, doses_quantity)) # SQL запрос для добавления лекарства.
        await db.commit() # Применение изменений к базе данных.

async def get_medicines_for_user(user_id: int) -> List[Tuple]:
    """
    Получение списка всех лекарств для конкретного пользователя по user_id.
    Возвращает список кортежей с информацией о лекарствах.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT name, dosage, dosage_unit, doses_quantity, reminder_time, remaining_quantity FROM medicines WHERE user_id = ?", (user_id,)) as cursor: # SQL запрос для получения лекарств пользователя, добавлен dosage_unit.
            return await cursor.fetchall() # Возвращает список найденных лекарств.

async def get_all_medicines_with_time() -> List[Tuple]:
    """
    Получение списка всех лекарств из базы данных вместе с временем приема.
    Используется для планировщика задач для проверки напоминаний.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT medicine_id, user_id, name, dosage, dosage_unit, reminder_time, remaining_quantity FROM medicines") as cursor: # SQL запрос для получения всех лекарств с временем приема, добавлен dosage_unit.
            return await cursor.fetchall() # Возвращает список всех лекарств.

async def decrement_medicine_quantity(medicine_id: int, dosage_to_decrement: int):
    """
    Уменьшение оставшегося количества доз лекарства в базе данных.
    Используется после отправки напоминания о приеме лекарства.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE medicines
            SET remaining_quantity = remaining_quantity - ?
            WHERE medicine_id = ?
        """, (dosage_to_decrement, medicine_id)) # SQL запрос для уменьшения количества оставшихся доз.
        await db.commit() # Применение изменений к базе данных.

async def get_medicine_by_id(medicine_id: int) -> Tuple | None:
    """
    Получение информации о лекарстве по его ID.
    Используется для проверки и обновления данных о лекарстве после отправки напоминания.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT name, dosage, dosage_unit, doses_quantity, reminder_time, remaining_quantity, user_id FROM medicines WHERE medicine_id = ?", (medicine_id,)) as cursor: # SQL запрос для получения лекарства по ID, добавлен dosage_unit.
            return await cursor.fetchone() # Возвращает информацию о лекарстве или None, если не найдено.

async def delete_medicine(medicine_id: int):
    """
    Удаление лекарства из базы данных по его ID.
    Используется, когда количество оставшихся доз становится равным нулю.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM medicines WHERE medicine_id = ?", (medicine_id,)) # SQL запрос для удаления лекарства.
        await db.commit() # Применение изменений к базе данных.

async def delete_medicine_by_name_and_user(user_id: int, medicine_name: str) -> bool:
    """
    Удаление лекарства из базы данных по имени лекарства и user_id.
    Возвращает True, если лекарство было удалено, и False, если нет (например, лекарство не найдено).
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM medicines WHERE user_id = ? AND name = ?", (user_id, medicine_name)) # SQL запрос для удаления лекарства по имени и user_id.
        await db.commit() # Применение изменений к базе данных.
        return cursor.rowcount > 0 # Возвращает True, если удалено больше 0 строк (т.е. лекарство было найдено и удалено).