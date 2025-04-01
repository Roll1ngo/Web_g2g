import os
import sys
import subprocess
import signal
import time
from pathlib import Path


def kill_process_on_port(port):
    try:
        print(f"Спроба звільнити порт {port}...")
        # Для Linux
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True
        )

        if result.stdout:
            pids = result.stdout.strip().split()
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"Успішно завершено процес з PID {pid}")
                    time.sleep(1)  # Даємо системі час звільнити порт
                except ProcessLookupError:
                    print(f"Процес {pid} вже завершено")
        else:
            print(f"На порту {port} немає запущених процесів")
    except Exception as e:
        print(f"Помилка при завершенні процесів: {str(e)}")


def run_django_server():
    try:
        # Визначаємо абсолютний шлях
        project_dir = Path(__file__).parent.resolve()
        manage_path = project_dir / "manage.py"

        print(f"Шлях до manage.py: {manage_path}")

        if not manage_path.exists():
            raise FileNotFoundError(f"Файл manage.py не знайдено за шляхом: {manage_path}")

        # Використовуємо Python з поточного середовища
        python = sys.executable
        print(f"Використовуємо Python: {python}")

        # Запускаємо сервер з явним вказівкам порту
        server = subprocess.Popen(
            [python, str(manage_path), "runserver", "127.0.0.1:8000"],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        print("Сервер Django запускається...")
        print(f"PID процесу: {server.pid}")

        # Вивід логів у реальному часі
        while True:
            output = server.stdout.readline()
            if not output and server.poll() is not None:
                break
            if output:
                print(output.strip())

        return server.wait()

    except KeyboardInterrupt:
        print("\nОтримано Ctrl+C - зупиняємо сервер...")
        server.terminate()
        server.wait()
        return 0
    except Exception as e:
        print(f"КРИТИЧНА ПОМИЛКА: {str(e)}")
        if 'server' in locals():
            server.terminate()
        return 1


if __name__ == "__main__":
    kill_process_on_port(8000)
    sys.exit(run_django_server())