import sys
sys.dont_write_bytecode = True

import asyncio
import logging

from maxo import Bot, Dispatcher
from maxo.fsm.storages.memory import MemoryStorage

from config import BOT_TOKEN, init_logger
from data.database import init_db, async_session_maker
from bot.handlers.user_handlers import router as user_router
from bot.middlewares.db import DbSessionMiddleware

init_logger()

async def main():
    await init_db()

    dp = Dispatcher(storage=MemoryStorage())
    bot = Bot(token=BOT_TOKEN)

    db_middleware = DbSessionMiddleware(async_session_maker)
    user_router.bot_started.middleware(db_middleware)
    user_router.message_created.middleware(db_middleware)
    user_router.message_callback.middleware(db_middleware)

    dp.include(user_router)

    logging.info(msg="Бот запущен.")

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.info(msg="Бот запускается...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info(msg="Бот выключен разработчиком.")
    except Exception as e:
        logging.error(msg=f"Бот не запустился, ошибка: {e}")
