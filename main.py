import sys
sys.dont_write_bytecode = True

import asyncio
import logging

from maxo import Bot, Dispatcher
from maxo.fsm.storages.memory import MemoryStorage

from config import BOT_TOKEN, init_logger
from data.database import init_db
from bot.handlers.user_handlers import router as user_router

init_logger()

async def main():
    await init_db()

    dp = Dispatcher(storage=MemoryStorage())
    bot = Bot(token=BOT_TOKEN)

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
    
    
