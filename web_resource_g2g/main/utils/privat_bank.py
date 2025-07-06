import requests
import json
import datetime
import os
import re  # Для парсингу часу з файлу
from django.conf import settings


def get_privatbank_usd_uah_exchange_rate_from_api():
    """
    Отримує курс долара США до гривні з API ПриватБанку.
    """
    url = "https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Викликає HTTPError для поганих відповідей (4xx або 5xx)
        data = response.json()

        usd_rate = None
        for rate in data:
            if rate.get('ccy') == 'USD' and rate.get('base_ccy') == 'UAH':
                usd_rate = rate
                break

        if usd_rate:
            buy_rate = float(usd_rate.get('buy'))
            sale_rate = float(usd_rate.get('sale'))
            # Повертаємо словник з курсами купівлі та продажу
            return {"buy": buy_rate, "sale": sale_rate}
        else:
            print("Курс USD до UAH не знайдено в відповіді API.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Помилка при запиті до API ПриватБанку: {e}")
        return None
    except json.JSONDecodeError:
        print("Помилка декодування JSON відповіді.")
        return None
    except ValueError as e:
        print(f"Помилка конвертації даних: {e}")
        return None


def save_rate_to_file(rate_data, filename="privatbank_rates.log"):
    """
    Зберігає дані про курс у файл разом із часовою міткою.

    Args:
        rate_data (dict): Словник, що містить ключі 'buy' та 'sale' для курсу.
        filename (str): Ім'я файлу для запису.
    """
    if rate_data:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            f"{timestamp} | Купівля {rate_data['buy']:.2f}, Продаж {rate_data['sale']:.2f}\n"
        )
        try:
            # Записуємо тільки останній запис, перезаписуючи файл
            with open(filename, "w", encoding="utf-8") as f:
                f.write(log_entry)
            print(f"Запис успішно оновлено у {filename}")
        except IOError as e:
            print(f"Помилка запису у файл {filename}: {e}")
    else:
        print("Немає даних для запису у файл.")


def get_latest_rate_from_file(filename="privatbank_rates.log"):
    """
    Читає останній записаний курс та час з файлу.

    Returns:
        tuple: (rate_data, timestamp) якщо знайдено, інакше (None, None).
    """
    if not os.path.exists(filename):
        return None, None

    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return None, None

            # Отримуємо останній рядок
            last_line = lines[-1].strip()

            # Парсимо час та дані
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| Купівля (\d+\.\d{2}), Продаж (\d+\.\d{2})",
                             last_line)
            if match:
                timestamp_str = match.group(1)
                buy_rate = float(match.group(2))
                sale_rate = float(match.group(3))

                timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                rate_data = {"buy": buy_rate, "sale": sale_rate}
                return rate_data, timestamp
            else:
                print(f"Не вдалося розпарсити останній рядок у файлі: {last_line}")
                return None, None
    except Exception as e:
        print(f"Помилка читання файлу {filename}: {e}")
        return None, None


def get_current_privatbank_rate(filename="privatbank_rates.log"):
    """
    Отримує курс долара до гривні, використовуючи файл кешу.
    Оновлює кеш, якщо дані застаріли.
    """
    current_time = datetime.datetime.now()

    # Спроба отримати останній курс з файлу
    last_rate, last_timestamp = get_latest_rate_from_file(filename)

    if last_rate and last_timestamp:
        time_difference = current_time - last_timestamp
        if time_difference.total_seconds() < settings.PRIVAT_BANK_RATE_UPDATE_INTERVAL_MINUTES * 60:
            return last_rate
        else:
            print(f"Курс застарів (оновлено {last_timestamp}). Оновлюємо...")
    else:
        print("Файл курсу відсутній або порожній. Отримуємо новий курс...")

    # Отримуємо новий курс з API
    new_rate = get_privatbank_usd_uah_exchange_rate_from_api()
    if new_rate:
        save_rate_to_file(new_rate, filename)
        return new_rate
    else:
        print("Не вдалося отримати курс з API. Повернення None.")
        return None


if __name__ == "__main__":
    # Приклад використання:
    privat_bank_rate = get_current_privatbank_rate()
    if privat_bank_rate:
        print("\nПоточний курс ПриватБанку:")
        print(f"Купівля: {privat_bank_rate['buy']:.2f}")
        print(f"Продаж:  {privat_bank_rate['sale']:.2f}")
    else:
        print("Не вдалося отримати курс ПриватБанку.")
