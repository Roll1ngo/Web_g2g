import os
import subprocess
import signal
import sys


def kill_process_on_port(port):
    try:
        # Знайти PID процесу, котрий використовує порт
        result = subprocess.run(
            ["netstat", "-ano", "|", "findstr", f":{port}"],
            capture_output=True, text=True, shell=True
        )
        lines = result.stdout.splitlines()
        for line in lines:
            if f":{port}" in line:
                parts = line.split()
                pid = parts[-1]  # Останній елемент — це PID
                # Завершити процес
                subprocess.run(["taskkill", "/PID", pid, "/F"], check=True)
                print(f"Процес з PID {pid} завершено.")
                return
        print(f"Процесів, які використовують порт {port}, не знайдено.")
    except Exception as e:
        print(f"Помилка: {e}")


def run_django_server():
    # Отримуємо шлях до Python інтерпретатора у віртуальному середовищі
    python_path = sys.executable

    # Запускаємо Django сервер з використанням цього шляху
    django_process = subprocess.Popen([python_path, "manage.py", "runserver"])

    try:
        # Чекаємо завершення Django сервера (Ctrl+C)
        django_process.wait()
    except KeyboardInterrupt:
        print("Отримано сигнал переривання. Завершуємо процеси...")
        django_process.terminate()  # Завершуємо Django сервер
        print("Процеси завершено.")


if __name__ == "__main__":
    port = 8000
    kill_process_on_port(port)

    run_django_server()

