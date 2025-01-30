import os
import subprocess


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
    os.system("python manage.py runserver")


if __name__ == "__main__":
    port = 8000
    kill_process_on_port(port)
    run_django_server()
