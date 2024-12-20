from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Константы для состояний в диалоге
(SET_NAME, SET_SCHEDULE, SET_QUANTITY, SET_REMINDER) = range(4)

# Хранилище данных о лекарствах
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Приветствие и начало настройки лекарства."""
    await update.message.reply_text(
        "Здравствуйте! Я помогу вам не забывать о приеме лекарств.\n\n"
        "Давайте начнем с указания лекарства. Напишите название лекарства:"
    )
    return SET_NAME

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение названия лекарства и переход к настройке расписания."""
    context.user_data['medicine_name'] = update.message.text
    await update.message.reply_text(
        f"Отлично! Сколько раз в день вы принимаете '{update.message.text}'?\n"
        "Например: 1, 2 или 3 раза в день."
    )
    return SET_SCHEDULE

async def set_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение расписания приема лекарства и переход к количеству."""
    try:
        frequency = int(update.message.text)
        if frequency < 1 or frequency > 10:
            raise ValueError("Число вне допустимого диапазона")
        context.user_data['frequency'] = frequency
        await update.message.reply_text(
            f"Хорошо! Вы принимаете лекарство {frequency} раз(а) в день.\n"
            "Теперь напишите, сколько доз лекарства у вас осталось."
        )
        return SET_QUANTITY
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите корректное число (от 1 до 10)."
        )
        return SET_SCHEDULE

async def set_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение количества лекарства и завершение настройки."""
    try:
        quantity = int(update.message.text)
        if quantity <= 0:
            raise ValueError("Количество должно быть положительным числом.")
        context.user_data['quantity'] = quantity
        await update.message.reply_text(
            f"Вы указали, что у вас осталось {quantity} доз лекарства.\n"
            "Я буду напоминать вам о приеме и сообщу, когда запасы будут подходить к концу.\n\n"
            "Напоминания настроены! Чтобы посмотреть текущие настройки, введите /status."
        )
        schedule_reminders(context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите положительное число."
        )
        return SET_QUANTITY

def schedule_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Планирование напоминаний на день."""
    frequency = context.user_data['frequency']
    intervals = [24 // frequency * i for i in range(frequency)]
    for hours in intervals:
        context.job_queue.run_once(
            send_reminder,
            when=hours * 60 * 60,  # Конвертация часов в секунды
            context=context.user_data,
            name=f"reminder_{hours}",
        )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка напоминания пользователю."""
    medicine_name = context.job.context.get('medicine_name', 'ваше лекарство')
    chat_id = context.job.context['chat_id']
    quantity = context.job.context.get('quantity', 0)

    # Уменьшаем запас лекарства
    if quantity > 0:
        context.job.context['quantity'] -= 1
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Запасы '{medicine_name}' закончились! Пожалуйста, купите новую упаковку."
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Напоминание: пора принять '{medicine_name}'.\n"
        f"Осталось: {context.job.context['quantity']} доз(ы)."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображение текущих настроек пользователя.

"""
    medicine_name = context.user_data.get('medicine_name', 'не указано')
    frequency = context.user_data.get('frequency', 'не указано')
    quantity = context.user_data.get('quantity', 'не указано')
    await update.message.reply_text(
        f"Текущие настройки:\n"
        f"Лекарство: {medicine_name}\n"
        f"Частота приема: {frequency} раз(а) в день\n"
        f"Остаток: {quantity} доз(ы)."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    await update.message.reply_text(
        "Настройка отменена. Вы можете начать заново, введя команду /start."
    )
    return ConversationHandler.END

def main() -> None:
    """Запуск бота."""
    # Замените TOKEN на токен вашего бота
    TOKEN = "твой токен"
    application = Application.builder().token(TOKEN).build()

    # Обработчик диалогов
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            SET_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_schedule)],
            SET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_quantity)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрация обработчиков
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("status", status))

    # Запуск бота
    application.run_polling()

if name == "__main__":
    main()
