# your_app_name/management/commands/create_missing_temp_passwords.py
import random

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from main.models import Sellers
from main import crud as main_crud
from user_profile.models import WithdrawalRequest

# Якщо TemporaryPassword знаходиться у users.models:
# from users.models import TemporaryPassword


User = get_user_model()

class Command(BaseCommand):
    help = 'Створює записи WithdrawalRequest для всіх користувачів, у яких їх немає.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Починається перевірка та створення WithdrawalRequest...'))

        created_count = 0
        skipped_count = 0

        # Отримуємо всіх користувачів
        all_sellers= Sellers.objects.all()

        for seller in all_sellers:
            user = seller.auth_user
            try:
                # Перевіряємо, чи існує запис TemporaryPassword для цього користувача
                if not WithdrawalRequest.objects.filter(user=user).exists():
                    # Якщо запису немає, створюємо новий
                    WithdrawalRequest.objects.create(
                        user=user,
                        withdraw_type='fixed_15_30',
                        payment_method = random.choice(['visa_mastercard', 'payoneer']),
                        commission_rate = random.choice([3,6]),
                        status = random.choice(['pending', 'approved']),
                        payment_details = {
                            "account_info": "1234567890"},
                    )
                    self.stdout.write(self.style.SUCCESS(f"Створено запис WithdrawalRequest для користувача: {user.username} (ID: {user.id})"))
                    created_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"Запис WithdrawalRequest для користувача {user.username} (ID: {user.id}) вже існує. Пропущено."))
                    skipped_count += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Помилка при обробці користувача {user.username} (ID: {user.id}): {e}"))
                # Не кидаємо CommandError, щоб продовжити обробку інших користувачів
                # якщо це одноразовий скрипт для заповнення

        self.stdout.write(self.style.SUCCESS(f'Завершено обробку. Створено {created_count} нових записів, пропущено {skipped_count} існуючих.'))
        self.stdout.write(self.style.SUCCESS('Операцію завершено.'))

