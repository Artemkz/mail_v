import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.web.routes import router as web_router
from app.config import settings
from app.database import init_db
from app.services.collector_service import collect_from_mailboxes
from app.database import async_session


async def _collector_loop() -> None:
  while True:
    try:
      async with async_session() as db:
        await collect_from_mailboxes(db)
    except Exception as exc:
      print(f"Фоновый сборщик: ошибка — {exc}")
    await asyncio.sleep(settings.collector_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
  await init_db()
  collector_task = asyncio.create_task(_collector_loop())
  yield
  collector_task.cancel()
  try:
    await collector_task
  except asyncio.CancelledError:
    pass


app = FastAPI(
  title="Mail Client Server",
  description=(
    "Сервер почтового клиента с IMAP, сбором писем с внешних ящиков, "
    "поиском по первым 3 символам слов и автоматической сортировкой по отправителям."
  ),
  version="1.0.0",
  lifespan=lifespan,
)

app.include_router(web_router)
app.include_router(api_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
  return {"status": "ok"}
