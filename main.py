import asyncio
import uvicorn
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import os
import logging
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем бота
import max_bot

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Запуск приложения...")
    
    # Запускаем бота в фоне (но без polling)
    max_task = asyncio.create_task(max_bot.run_max_bot())
    logger.info("✅ Бот запущен в фоновом режиме")
    
    yield
    
    # При остановке сервера корректно завершаем бота
    logger.info("🛑 Остановка приложения...")
    max_task.cancel()
    try:
        await max_task
    except asyncio.CancelledError:
        logger.info("✅ Бот остановлен")
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok", "bot": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/debug")
async def debug():
    """Эндпоинт для отладки"""
    return {
        "token_set": bool(os.getenv("MAX_BOT_TOKEN")),
        "data_path": os.getenv("DATA_PATH", "/app/data"),
        "db_exists": os.path.exists(os.path.join(os.getenv("DATA_PATH", "/app/data"), "bot.db")),
        "webhook_url": os.getenv("WEBHOOK_URL", "не задан")
    }

@app.post("/webhook")
async def webhook(request: Request):
    """Обработка webhook-обновлений от MAX"""
    try:
        body = await request.body()
        data = json.loads(body)
        print(f"📨 Webhook получен: {data}", flush=True)
        
        # Обрабатываем обновление
        max_bot.process_update(data)
        return {"status": "ok"}
    except Exception as e:
        print(f"⚠️ Ошибка webhook: {e}", flush=True)
        return {"status": "error"}, 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    logger.info(f"🔊 Запуск сервера на порту {port}")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
