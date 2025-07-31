import os
import subprocess
import platform
import time
import sys

PORT = 8000
HOST = '127.0.0.1'  # Змінено з '0.0.0.0' на '127.0.0.1'
APP_MODULE = 'web_resource_g2g.wsgi:application'
POETRY_BIN = 'poetry'  # Команда для Poetry
GUNICORN_BIN = 'gunicorn'  # Команда для Gunicorn


def kill_process_on_port(port):
    """
    Знаходить і вбиває процес, який слухає вказаний порт.
    """
    os_name = platform.system()
    print(f"Спроба звільнити порт {port} на {os_name}...")

    if os_name == "Linux" or os_name == "Darwin":
        try:
            # Спрощена команда - lsof -t -i :<port> повертає PID процесу
            command = f"lsof -t -i :{port} -sTCP:LISTEN"
            process = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=False
            )

            if process.returncode == 0 and process.stdout.strip():
                pids = process.stdout.strip().split('\n')
                for pid in pids:
                    pid = pid.strip()
                    if pid:
                        print(f"Знайдено процес з PID {pid} на порту {port}. Спроба зупинити...")
                        subprocess.run(f"kill -9 {pid}", shell=True, check=True)
                        print(f"Успішно завершено процес з PID {pid}")
                time.sleep(2)  # Затримка для звільнення порту
            else:
                print(f"На порту {port} немає запущених процесів.")
        except Exception as e:
            print(f"Помилка при звільненні порту: {e}")


def is_port_in_use(port):
    """Перевіряє, чи порт зайнятий."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return False
        except socket.error:
            return True

def run_gunicorn():
    """
    Запускає Gunicorn за допомогою Poetry.
    """
    print(f"Використовуємо Python: {sys.executable}")
    print("Сервер Django запускається...")

    # Перевіряємо, чи poetry gunicorn встановлено у віртуальному середовищі
    try:
        subprocess.run(f"{POETRY_BIN} run {GUNICORN_BIN} --version", shell=True, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            f"Помилка: {GUNICORN_BIN} не знайдено або не встановлено через {POETRY_BIN}. Переконайтеся, що ви активували віртуальне середовище або що gunicorn встановлено у вашому poetry-проекті.")
        sys.exit(1)

    try:
        # Побудуйте команду Gunicorn з урахуванням Poetry
        gunicorn_command = [
            POETRY_BIN, 'run', GUNICORN_BIN,
            APP_MODULE,
            '--bind', f"{HOST}:{PORT}",
            '--reuse-port'  # Додано для вирішення проблеми Address already in use
        ]

        # Використовуйте subprocess.run без shell=True для кращої безпеки,
        # але для poetry run іноді це може бути складніше без shell=True.
        # Для простоти та сумісності з 'poetry run' залишимо shell=True.
        # Однак, більш надійно було б активувати venv, а потім запускати gunicorn напряму.
        print(f"Запускаємо команду: {' '.join(gunicorn_command)}")
        subprocess.run(' '.join(gunicorn_command), shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Помилка при запуску Gunicorn: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nОтримано Ctrl+C - зупиняємо сервер...")
        sys.exit(0)


if __name__ == "__main__":
    kill_process_on_port(PORT)

    # Додаткова перевірка порту
    if is_port_in_use(PORT):
        print(f"Порт {PORT} все ще зайнятий після спроби звільнення!")
        sys.exit(1)

    print(f"Очікування 5 секунд для повного звільнення порту {PORT}...")
    time.sleep(5)
    run_gunicorn()
