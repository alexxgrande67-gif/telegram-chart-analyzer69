import os
import json
import logging
import sys
from telegram import Update, Bot
from telegram.ext import Dispatcher, MessageHandler, filters

# --- Настройки ---
# Путь к модулю анализа
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорт асинхронной функции анализа
from analysis_engine.gemini_analyzer import analyze_with_gemini

# Получаем токены из переменных окружения Vercel
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
DOWNLOAD_DIR = "/tmp/" # Временная директория для Vercel

logging.basicConfig(level=logging.INFO)

# --- Обработчик фото ---
async def handle_photo(update: Update, context) -> None:
    """Скачивает фото, анализирует через Gemini и отправляет ответ."""
    
    if not update.message or not update.message.photo or not TELEGRAM_BOT_TOKEN:
        return

    bot = context.bot
    
    # 1. Получаем информацию о самом большом фото
    photo_file = await update.message.photo[-1].get_file()
    
    # 2. Формируем временный путь к файлу
    file_name = f"{photo_file.file_unique_id}.jpg"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    
    await update.message.reply_text("⏳ Идет загрузка и анализ изображения через Gemini AI...", 
                                    chat_id=update.message.chat_id)

    try:
        # 3. Скачиваем файл
        await photo_file.download_to_memory(file_path)
        
        # 4. Анализируем файл с помощью Gemini
        # Асинхронный вызов
        analysis_result = await analyze_with_gemini(file_path) 
        
        # 5. Отправляем результат
        await update.message.reply_markdown(analysis_result, chat_id=update.message.chat_id)

    except Exception as e:
        logging.error(f"Критическая ошибка при обработке: {e}", exc_info=True)
        await update.message.reply_text(f"❌ **Критическая ошибка:** {e}", 
                                        chat_id=update.message.chat_id)
    
    finally:
        # Очистка временного файла
        if os.path.exists(file_path):
            os.remove(file_path)


# --- Основная HTTP-функция для Vercel ---
async def handler(request):
    """
    Основная функция, вызываемая Vercel при получении HTTP-запроса (Webhook).
    """
    if request.method != 'POST' or not TELEGRAM_BOT_TOKEN:
        return {"statusCode": 405, "body": "Method Not Allowed or Token Missing"}

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Invalid JSON"}

    # Создаем объекты
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    application = Dispatcher(bot=bot, update_queue=None)

    # Регистрируем обработчик для фото
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Обрабатываем входящее обновление
    update = Update.de_json(data=body, bot=bot)
    
    await application.process_update(update)

    return {"statusCode": 200, "body": "OK"}
