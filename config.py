import os
import dotenv
import logging

dotenv.load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

BOT_TOKEN = os.getenv("BOT_TOKEN")

def init_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.getLogger("aiogram").setLevel(logging.ERROR)
    logging.info(msg="Логи подключены")