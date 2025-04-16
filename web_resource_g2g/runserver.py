import os
import sys
import subprocess
import signal
import time
import platform
from pathlib import Path


def kill_process_on_port(port):
    system_name = platform.system()
    try:
        print(f"Спроба звільнити порт {port} на {system_name}...")

        if system_name == "Windows":
            # Windows: використовуємо netstat і taskkill
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True,
                capture_output=True,
                text=True
            )

            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.strip().split()
                if parts and len(parts) >= 5:
                    pid = parts[-1]
                    pids.add(pid)

            for pid in pids:
                subprocess.run(['taskkill', '/F', '/PID', pid], shell=True)
                print(f"Процес з PID {pid} завершено")
            if not pids:
                print(f"На порту {port} немає активних процесів")

        elif system_name in ["Linux", "Darwin"]:
            # Linux/MacOS: використовуємо lsof
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
                        time.sleep(1)
                    except ProcessLookupError:
                        print(f"Процес {pid} вже завершено")
            else:
                print(f"На порту {port} немає запущених процесів")
        else:
            print(f"ОС {system_name} не підтримується для автоматичного завершення процесів.")

    except Exception as e:
        print(f"Помилка при завершенні процесів: {str(e)}")


def run_django_server():
    try:
        project_dir = Path(__file__).parent.resolve()
        manage_path = project_dir / "manage.py"

        print(f"Шлях до manage.py: {manage_path}")

        if not manage_path.exists():
            raise FileNotFoundError(f"Файл manage.py не знайдено за шляхом: {manage_path}")

        python = sys.executable
        print(f"Використовуємо Python: {python}")

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
