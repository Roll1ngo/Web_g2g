import asyncio
import os
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from dotenv import load_dotenv

from .utils.logger_config import logger

load_dotenv()
BOT_TOKEN = os.getenv('TG_TOKEN')


async def send_messages_to_users(seller_id, seller_name, message):
    bot = Bot(token=BOT_TOKEN)

    # ID отримувачів
    recipients = { 190861163: 'Vlad'}   # 822070279: 'Vitaliy' seller_id: seller_name,

    try:
        for tg_id, name in recipients.items():
            await bot.send_message(chat_id=tg_id, text=message)
            logger.info(f'send_message for tg_id__{tg_id} - name__{name}, message__{message}')
            print(f"✅ Повідомлення надіслано до {name}")
            await asyncio.sleep(2)  # Затримка між відправками (не обов’язково)
        return True
    except TelegramNetworkError as e:
        print(f"❌ Помилка мережі: {e}")
    except Exception as e:
        print(f"❌ Помилка надсилання повідомлення: {e}")
    finally:
        await bot.session.close()


def send_messages_sync(seller_id, seller_name, message):
    """ Виклик асинхронної функції з синхронного коду """
    response = asyncio.run(send_messages_to_users(seller_id, seller_name, message))
    return True if response else False


# 🔹 Використання:
if __name__ == "__main__":
    test_message = "Тестове повідомлення"
    test_seller_id = 123456789  # Замініть на справжній ID продавця
    send_messages_sync(test_seller_id, test_message)
