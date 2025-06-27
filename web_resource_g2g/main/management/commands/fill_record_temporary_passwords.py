# your_app_name/management/commands/create_missing_temp_passwords.py

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
# Переконайтеся, що ви імпортуєте TemporaryPassword з правильного місця
# Наприклад, якщо TemporaryPassword знаходиться у main.models:
from main.models import TemporaryPassword
# Якщо TemporaryPassword знаходиться у users.models:
# from users.models import TemporaryPassword


User = get_user_model()

class Command(BaseCommand):
    help = 'Створює записи TemporaryPassword для всіх користувачів, у яких їх немає.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Починається перевірка та створення тимчасових паролів...'))

        created_count = 0
        skipped_count = 0

        # Отримуємо всіх користувачів
        all_users = User.objects.all()

        for user in all_users:
            try:
                # Перевіряємо, чи існує запис TemporaryPassword для цього користувача
                if not TemporaryPassword.objects.filter(user=user).exists():
                    # Якщо запису немає, створюємо новий
                    TemporaryPassword.objects.create(
                        user=user,
                        raw_password='DELETED', # Встановлюємо 'DELETED' як зазначено
                        # created_at заповниться автоматично завдяки auto_now_add=True в моделі
                        is_confirmed=True # Встановлюємо True як зазначено
                    )
                    self.stdout.write(self.style.SUCCESS(f"Створено запис TemporaryPassword для користувача: {user.username} (ID: {user.id})"))
                    created_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"Запис TemporaryPassword для користувача {user.username} (ID: {user.id}) вже існує. Пропущено."))
                    skipped_count += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Помилка при обробці користувача {user.username} (ID: {user.id}): {e}"))
                # Не кидаємо CommandError, щоб продовжити обробку інших користувачів
                # якщо це одноразовий скрипт для заповнення

        self.stdout.write(self.style.SUCCESS(f'Завершено обробку. Створено {created_count} нових записів, пропущено {skipped_count} існуючих.'))
        self.stdout.write(self.style.SUCCESS('Операцію завершено.'))

