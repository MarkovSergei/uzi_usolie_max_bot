import asyncio
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

import max_bot

@asynccontextmanager
async def lifespan(app: FastAPI):
    max_task = asyncio.create_task(max_bot.run_max_bot())
    yield
    max_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(__import__("os").getenv("PORT", 3000)))
