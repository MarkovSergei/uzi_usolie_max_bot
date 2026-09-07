import asyncio
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
import os

import max_bot

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаем бота в фоне
    max_task = asyncio.create_task(max_bot.run_max_bot())
    yield
    # При остановке сервера корректно завершаем бота
    max_task.cancel()
    try:
        await max_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok", "bot": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
