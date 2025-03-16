import asyncio
import os
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from dotenv import load_dotenv

from main.utils.logger_config import logger

load_dotenv()
BOT_TOKEN = os.getenv('TG_TOKEN')
admins_tgs = {'Vlad': 190861163, 'Vitaliy': 822070279}


async def send_messages_to_users(seller_tg, seller_name, message):
    bot = Bot(token=BOT_TOKEN)
    recipients = admins_tgs.copy()  # Створюємо копію словника, щоб не змінювати оригінал

    if seller_tg != admins_tgs['Vitaliy']:
        recipients.update({seller_name: seller_tg})

    try:
        for name, tg in recipients.items():
            await bot.send_message(chat_id=tg, text=message)
            logger.warning(f"Повідомлення надіслано до {name}")
            await asyncio.sleep(2)
        return True
    except TelegramNetworkError as e:
        logger.error(f"Помилка мережі: {e}")
    except Exception as e:
        logger.error(f"Помилка надсилання повідомлення: {e}")
    finally:
        await bot.session.close()


def send_messages_sync(seller_tg, seller_name, message):
    """ Виклик асинхронної функції з синхронного коду """
    response = asyncio.run(send_messages_to_users(seller_tg, seller_name, message))
    return True if response else False


# 🔹 Використання:
if __name__ == "__main__":
    test_message = "Тестове повідомлення"
    test_seller_id = 123456789  # Замініть на справжній ID продавця
    send_messages_sync(test_seller_id, 'test_name',  test_message)

