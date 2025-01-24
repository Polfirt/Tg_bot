# handlers.py
# Файл обработчиков команд и сообщений бота.
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import re
import logging
from utils import get_timezone_from_location, GeocoderTimedOut
from database import set_user_timezone, add_medicine, get_medicines_for_user, get_user_timezone, delete_medicine_by_name_and_user

# handlers.py
# aiogram: 3.x.x
# python: 3.9+

# Инициализация роутера для обработки сообщений.
router = Router()
logging.basicConfig(level=logging.INFO)

# --- States для FSM (машины состояний) ---
class TimezoneSetup(StatesGroup):
    # Состояние ожидания геолокации для установки часового пояса.
    WAITING_FOR_LOCATION = State()

class AddMedicine(StatesGroup):
    # Состояния для процесса добавления нового лекарства.
    WAITING_FOR_NAME = State() # Ожидание названия лекарства.
    WAITING_FOR_DOSAGE = State() # Ожидание дозировки.
    WAITING_FOR_DOSAGE_UNIT = State() # Ожидание единицы измерения дозировки.
    WAITING_FOR_QUANTITY = State() # Ожидание общего количества доз.
    WAITING_FOR_TIMES = State() # Ожидание времени приема (может быть несколько значений).

class DeleteMedicine(StatesGroup):
    # Состояния для процесса удаления лекарства.
    WAITING_FOR_MEDICINE_NAME_TO_DELETE = State() # Ожидание названия лекарства для удаления.

# --- Обработчики команд ---
@router.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    Предлагает пользователю отправить геолокацию для установки часового пояса.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить мою геолокацию", request_location=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True # Клавиатура исчезнет после первого использования.
    )
    await message.answer(
        "Привет! Я бот-напоминалка о приеме лекарств.\n"
        "Пожалуйста, отправьте свою геолокацию, чтобы я мог установить ваш часовой пояс.",
        reply_markup=keyboard
    )
    await state.set_state(TimezoneSetup.WAITING_FOR_LOCATION) # Установка состояния ожидания геолокации.

@router.message(Command("timezone"))
async def timezone_command_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /timezone.
    Повторно предлагает пользователю отправить геолокацию для изменения часового пояса.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить мою геолокацию", request_location=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Пожалуйста, отправьте свою геолокацию, чтобы установить часовой пояс.",
        reply_markup=keyboard
    )
    await state.set_state(TimezoneSetup.WAITING_FOR_LOCATION) # Установка состояния ожидания геолокации.


@router.message(TimezoneSetup.WAITING_FOR_LOCATION, F.content_type == types.ContentType.LOCATION)
async def location_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик геолокации, полученной от пользователя.
    Определяет часовой пояс на основе геолокации и сохраняет его в базе данных.
    """
    latitude = message.location.latitude
    longitude = message.location.longitude
    try:
        timezone = await get_timezone_from_location(latitude, longitude) # Получение часового пояса из utils.py.
        if timezone:
            await set_user_timezone(message.from_user.id, timezone) # Сохранение часового пояса в БД.
            await message.answer(f"Ваш часовой пояс установлен как: {timezone}. Теперь вы можете использовать команды бота.", reply_markup=types.ReplyKeyboardRemove())
        else:
            await message.answer("Не удалось определить часовой пояс по геолокации. Пожалуйста, попробуйте отправить геолокацию еще раз.", reply_markup=types.ReplyKeyboardRemove())
            await state.clear() # Сброс состояния.
    except GeocoderTimedOut:
        await message.answer("Извините, сервис определения часового пояса временно недоступен (timeout). Пожалуйста, попробуйте позже или убедитесь в стабильном интернет-соединении.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear() # Сброс состояния в случае timeout.
    except Exception as e: # Обработка других возможных ошибок геолокации
        logging.error(f"Ошибка при определении часового пояса: {e}")
        await message.answer("Произошла ошибка при определении часового пояса. Пожалуйста, попробуйте еще раз позже.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear() # Сброс состояния в случае ошибки.
    finally: # Гарантированное снятие состояния после попытки обработки геолокации.
        if await state.get_state() == TimezoneSetup.WAITING_FOR_LOCATION: # Проверка, что состояние еще установлено.
            await state.clear()


@router.message(TimezoneSetup.WAITING_FOR_LOCATION)
async def wrong_content_type_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик для некорректного типа контента, когда ожидается геолокация.
    Сообщает пользователю о необходимости отправить геолокацию через кнопку.
    """
    await message.answer("Пожалуйста, отправьте именно геолокацию, используя кнопку 'Отправить мою геолокацию'.")


@router.message(Command("add"))
async def add_medicine_command_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /add.
    Начинает процесс добавления нового лекарства, проверяя установлен ли часовой пояс.
    """
    user_timezone = await get_user_timezone(message.from_user.id) # Проверка, установлен ли часовой пояс.
    if not user_timezone:
        await message.answer("Перед добавлением лекарств, пожалуйста, установите свой часовой пояс, используя команду /start или /timezone и отправив геолокацию.")
        return
    await state.set_state(AddMedicine.WAITING_FOR_NAME) # Установка состояния ожидания названия лекарства.
    await message.answer("Пожалуйста, введите название лекарства:")

@router.message(AddMedicine.WAITING_FOR_NAME)
async def get_medicine_name(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_NAME.
    Получает название лекарства от пользователя и переходит к следующему состоянию.
    """
    await state.update_data(medicine_name=message.text) # Сохранение названия лекарства в FSMContext.
    await state.set_state(AddMedicine.WAITING_FOR_DOSAGE) # Переход к состоянию ожидания дозировки.
    await message.answer("Теперь введите дозировку лекарства (можно несколько через запятую, только числа, например '1, 0.5, 2'):")

@router.message(AddMedicine.WAITING_FOR_DOSAGE)
async def get_medicine_dosage(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_DOSAGE.
    Получает дозировку лекарства от пользователя и переходит к следующему состоянию - выбору ед. измерения.
    """
    dosages_text = message.text
    dosages = [d.strip() for d in dosages_text.split(',')] # Разделение дозировок, если их несколько.
    for dosage in dosages:
        try:
            float(dosage) # Проверка, что все введенные значения - числа.
        except ValueError:
            await message.answer("Пожалуйста, вводите только числа в качестве дозировки (например, '1' или '0.5'). Если дозировок несколько, разделите их запятой.")
            return
    await state.update_data(medicine_dosage=dosages_text) # Сохранение дозировки в FSMContext.
    await state.set_state(AddMedicine.WAITING_FOR_DOSAGE_UNIT) # Переход к состоянию ожидания выбора ед. измерения.
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Таблетки"),
                KeyboardButton(text="гр"),
                KeyboardButton(text="мл")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Выберите единицу измерения дозировки:", reply_markup=keyboard)


@router.message(AddMedicine.WAITING_FOR_DOSAGE_UNIT, F.text.in_({"Таблетки", "гр", "мл"}))
async def get_dosage_unit(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_DOSAGE_UNIT.
    Получает единицу измерения дозировки от пользователя и переходит к следующему состоянию.
    """
    dosage_unit = message.text
    await state.update_data(medicine_dosage_unit=dosage_unit) # Сохранение ед. измерения в FSMContext.
    await state.set_state(AddMedicine.WAITING_FOR_QUANTITY) # Переход к состоянию ожидания количества.
    await message.answer("Введите общее количество доз в упаковке (целое число):", reply_markup=types.ReplyKeyboardRemove())


@router.message(AddMedicine.WAITING_FOR_DOSAGE_UNIT)
async def wrong_dosage_unit_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик для некорректного выбора ед. измерения.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Таблетки"),
                KeyboardButton(text="гр"),
                KeyboardButton(text="мл")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Пожалуйста, выберите единицу измерения, используя кнопки:", reply_markup=keyboard)


@router.message(AddMedicine.WAITING_FOR_QUANTITY)
async def get_medicine_quantity(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_QUANTITY.
    Получает общее количество доз лекарства от пользователя и переходит к следующему состоянию.
    Проверяет, что введено целое число.
    """
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите целое число для общего количества доз.")
        return
    await state.update_data(medicine_quantity=int(message.text)) # Сохранение количества доз в FSMContext.
    await state.set_state(AddMedicine.WAITING_FOR_TIMES) # Переход к состоянию ожидания времени приема.
    await message.answer("Введите время приема лекарства (можно несколько через запятую, например '8:00, 12:30, 20:00'):")

@router.message(AddMedicine.WAITING_FOR_TIMES)
async def get_medicine_time(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_TIMES.
    Получает время приема лекарства от пользователя, проверяет формат и сохраняет данные лекарства.
    """
    times_text = message.text
    times = [t.strip() for t in times_text.split(',')] # Разделение времени приема, если их несколько.
    time_format = r"^([0-9]|[01][0-9]|2[0-3]):[0-5][0-9]$" # Регулярное выражение для формата времени ЧЧ:ММ.

    for time_str in times:
        if not re.match(time_format, time_str):
            await message.answer("Неверный формат времени: '{}'. Пожалуйста, используйте формат ЧЧ:ММ (например, 8:00 или 21:30) для всех времен.".format(time_str))
            return # Выход из функции, если формат времени неверный.

    await state.update_data(medicine_time=times_text) # Сохранение времени приема в FSMContext.

    data = await state.get_data() # Получение всех данных из FSMContext.
    medicine_name = data.get("medicine_name")
    medicine_dosage = data.get("medicine_dosage")
    medicine_dosage_unit = data.get("medicine_dosage_unit")
    medicine_quantity = data.get("medicine_quantity")
    medicine_time = data.get("medicine_time")

    dosages_list = [d.strip() for d in medicine_dosage.split(',')] # Разделение дозировок для проверки соответствия количеству времен.
    times_list = [t.strip() for t in medicine_time.split(',')] # Разделение времени для проверки соответствия количеству дозировок.

    if len(dosages_list) != len(times_list):
        await message.answer("Количество дозировок и времен приема должно совпадать. Пожалуйста, проверьте введенное время и дозировки.")
        return

    await add_medicine(message.from_user.id, medicine_name, medicine_dosage, medicine_dosage_unit, medicine_quantity, medicine_time) # Добавление лекарства в базу данных, передаем dosage_unit.
    await message.answer(f"Лекарство '{medicine_name}' (дозировки: {medicine_dosage} {medicine_dosage_unit}), время приема: {medicine_time} добавлено.")
    await state.clear() # Сброс состояния после успешного добавления лекарства.

@router.message(Command("status"))
async def status_command_handler(message: types.Message) -> None:
    """
    Обработчик команды /status.
    Выводит список добавленных лекарств для пользователя.
    """
    medicines = await get_medicines_for_user(message.from_user.id) # Получение списка лекарств из базы данных.
    if medicines:
        response = "Ваши лекарства:\n"
        for medicine in medicines:
            name, dosage, dosage_unit, quantity, time, remaining_quantity = medicine # Распаковка данных о лекарстве, добавлен dosage_unit.
            response += f"- {name} (дозировка: {dosage} {dosage_unit}), {quantity} доз в упаковке, осталось: {remaining_quantity}, время приема: {time}\n"
        await message.answer(response)
    else:
        await message.answer("У вас пока нет добавленных лекарств. Используйте команду /add для добавления.")

@router.message(Command("delete"))
async def delete_medicine_command_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /delete.
    Запрашивает у пользователя название лекарства для удаления.
    """
    medicines = await get_medicines_for_user(message.from_user.id)
    if medicines:
        response = "Список ваших лекарств для удаления:\n"
        for index, medicine in enumerate(medicines):
            name, dosage, dosage_unit, quantity, time, remaining_quantity = medicine
            response += f"{index + 1}. {name} (дозировка: {dosage} {dosage_unit})\n"
        response += "\nВведите название лекарства, которое вы хотите удалить:"
        await message.answer(response)
        await state.set_state(DeleteMedicine.WAITING_FOR_MEDICINE_NAME_TO_DELETE) # Установка состояния ожидания ввода названия лекарства для удаления.
    else:
        await message.answer("У вас нет добавленных лекарств для удаления. Используйте команду /add, чтобы добавить лекарства.")

@router.message(DeleteMedicine.WAITING_FOR_MEDICINE_NAME_TO_DELETE)
async def get_medicine_name_to_delete(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик состояния WAITING_FOR_MEDICINE_NAME_TO_DELETE.
    Получает название лекарства от пользователя и удаляет его из базы данных.
    """
    medicine_name_to_delete = message.text
    user_id = message.from_user.id
    deleted = await delete_medicine_by_name_and_user(user_id, medicine_name_to_delete) # Попытка удаления лекарства.
    if deleted:
        await message.answer(f"Лекарство '{medicine_name_to_delete}' успешно удалено из списка напоминаний.")
    else:
        await message.answer(f"Не удалось найти и удалить лекарство '{medicine_name_to_delete}'. Пожалуйста, убедитесь, что название введено верно и лекарство существует в вашем списке.")
    await state.clear() # Сброс состояния после попытки удаления.


@router.message()
async def echo_handler(message: types.Message) -> None:
    """
    Обработчик для всех текстовых сообщений, не являющихся командами.
    Сообщает пользователю о непонимании команды.
    """
    await message.answer("Я не понимаю эту команду. Используйте /start, /add, /status, /delete или /timezone.")