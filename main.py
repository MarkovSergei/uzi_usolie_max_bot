import asyncio
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

import config
import database
import max_bot
import admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация базы
    database.init_db()

    # Запуск MAX-бота
    max_task = asyncio.create_task(max_bot.run_max_bot())

    yield

    # При остановке
    max_task.cancel()

app = FastAPI(lifespan=lifespan)

app.include_router(admin.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "uzi-usolie-max-bot"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
