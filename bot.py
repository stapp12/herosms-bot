import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import Config
from database import Database
from handlers import user, admin, payment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    config = Config()
    db = Database(config.DB_PATH)
    await db.init()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp["db"] = db

    dp.include_router(admin.router)
    dp.include_router(user.router)
    dp.include_router(payment.router)

    logger.info("הבוט מתחיל...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
