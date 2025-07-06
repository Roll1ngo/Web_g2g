import calendar
import datetime
import decimal

from django.db import models
from django.conf import settings  # Для посилання на стандартну модель User
from django.core.validators import MinValueValidator
from django.utils import timezone  # Для роботи з часовими поясами

from main.context_processors import get_current_privatbank_rate
from main.utils.logger_config import logger


class WithdrawalRequest(models.Model):
    """
    Модель для зберігання запитів на виведення коштів користувачами.
    """

    # Посилання на користувача, який робить запит
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests',
        verbose_name="Користувач",
        unique=True
    )

    # Сума коштів для виведення
    # Це поле буде використовуватися для 'custom'.
    # Для 'fixed_15_30' та 'do_not_withdraw' воно буде ігноруватися або встановлюватися в 0.
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],  # Мінімальна сума виведення
        verbose_name="Сума виведення",
        null=True,  # Дозволяємо бути NULL, якщо сума не потрібна (наприклад, для "Не виводити")
        blank=True  # Дозволяємо бути порожнім
    )
    converted_amount_uah = models.DecimalField(
        max_digits=12,  # Збільшена точність для більших сум в UAH
        decimal_places=2,
        verbose_name="Конвертована сума з урахуванням комісій (грн)",
        null=True,
        blank=True
    )
    # Варіанти виведення коштів
    WITHDRAW_TYPE_CHOICES = [
        ('fixed_15_30', '15 і 30 числа кожного місяця (вивести всю суму)'), # Оновлено
        ('custom', 'Терміновий вивід (протягом 24 годин)'),
        ('do_not_withdraw', 'Не виводити'),
    ]
    withdraw_type = models.CharField(
        max_length=30,  # Збільшено довжину для нових варіантів
        choices=WITHDRAW_TYPE_CHOICES,
        default='fixed_15_30',  # Встановлено початкове значення
        verbose_name="Тип виведення"
    )

    # Методи виведення коштів
    PAYMENT_METHOD_CHOICES = [
        ('payoneer', 'Payoneer'),
        ('visa_mastercard', 'Visa / Mastercard (грн)'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='payoneer',
        verbose_name="Метод виведення",
        null=True,  # Дозволяємо бути NULL, якщо метод не потрібен (наприклад, для "Не виводити")
        blank=True  # Дозволяємо бути порожнім
    )

    # Комісія, яка була застосована на момент запиту
    commission_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        verbose_name="Комісія (%)",
        null=True,  # Дозволяємо бути NULL, якщо комісія не застосовується
        blank=True  # Дозволяємо бути порожнім
    )

    # Запланована дата виведення (для всіх, крім "Не виводити")
    scheduled_withdrawal_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Запланована дата виведення"
    )

    # custom_withdrawal_date більше не використовується для вибору дати користувачем
    # але залишається як потенційний індикатор, що вивід терміновий (custom)
    custom_withdrawal_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Власна дата виведення"  # Назва поля залишається, хоча логіка змінилась
    )

    # Статус запиту на виведення
    STATUS_CHOICES = [
        ('pending', 'Очікує'),
        ('approved', 'Затверджено'),
        ('completed', 'Виконано'),
        ('rejected', 'Відхилено'),
        ('cancelled', 'Скасовано'),
        ('not_applicable', 'Не застосовується'),  # Для "Не виводити"
    ]
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )

    # Час створення запиту
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата створення"
    )

    # Час останнього оновлення запиту
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата оновлення"
    )

    # Поле для зберігання додаткової інформації (наприклад, номер рахунку Payoneer, номер картки)
    payment_details = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Деталі оплати"
    )

    class Meta:
        verbose_name = "Запит на виведення"
        verbose_name_plural = "Запити на виведення"
        ordering = ['-created_at']  # Сортування за датою створення (найновіші зверху)

    def __str__(self):
        if self.pk:
            return f"Запит #{self.pk} від {self.user.username} на {self.amount if self.amount else 'N/A'}$ ({self.status})"
        return f"Новий запит від {self.user.username} на {self.amount if self.amount else 'N/A'}$ ({self.status})"

    def save(self, *args, **kwargs):
        """
        Перевизначення методу save для автоматичного розрахунку комісії
        та встановлення запланованої дати виведення.
        """
        # Скидаємо amount, payment_method, commission_rate та scheduled_withdrawal_date
        # якщо обрано "Не виводити", щоб уникнути конфліктів у БД.
        if self.withdraw_type == 'do_not_withdraw':
            self.amount = None
            self.payment_method = None
            self.commission_rate = None
            self.scheduled_withdrawal_date = None
            self.payment_details = None
            self.status = 'not_applicable'  # Встановлюємо статус
        else:
            # Встановлюємо статус на 'pending' для інших типів виведення,
            # щоб скинути 'not_applicable', якщо він був встановлений раніше.
            if self.status == 'not_applicable': # Перевіряємо, чи був попередній статус 'not_applicable'
                self.status = 'pending' # Якщо так, скидаємо його на 'pending'
            # Якщо статус вже є 'pending' або іншим, він залишається без змін,
            # якщо тільки він не змінюється явно іншою логікою.

            # Розрахунок комісії
            if self.withdraw_type == 'custom':
                if self.payment_method == 'payoneer':
                    self.commission_rate = 3.00
                elif self.payment_method == 'visa_mastercard':
                    self.commission_rate = 9.00
            elif self.withdraw_type == 'fixed_15_30': # Оновлено
                if self.payment_method == 'payoneer':
                    self.commission_rate = 0.00
                elif self.payment_method == 'visa_mastercard':
                    self.commission_rate = 6.00

            # Розрахунок scheduled_withdrawal_date
            today_date = timezone.now().date()
            if self.withdraw_type == 'custom':
                # Для термінового виводу, встановлюємо дату на сьогодні (а "протягом 24 годин" це service level)
                self.scheduled_withdrawal_date = today_date
                self.custom_withdrawal_date = today_date  # Для цього типу виводу

                # Розрахунок конвертованої суми в гривнях тільки для типу 'custom'
                if self.amount and self.payment_method == 'visa_mastercard':
                    private_bank_rate = get_current_privatbank_rate().get('buy')
                    logger.info(f"Private bank rate: {private_bank_rate}")

                    # Розрахунок суми USD після відрахування комісії
                    # Переконайтеся, що commission_rate не є None перед використанням
                    if self.commission_rate is not None:
                        usd_with_commission = decimal.Decimal(self.amount) * (
                                    decimal.Decimal('1') - decimal.Decimal(self.commission_rate) / decimal.Decimal('100.00'))
                    else:
                        # Обробка випадку, якщо commission_rate чомусь None,
                        # хоча ваша логіка вище має його встановлювати.
                        # Можливо, варто підняти виняток або вважати комісію 0.
                        logger.warning("commission_rate is None for a custom withdrawal.")
                        usd_with_commission = self.amount

                    # Викликаємо функцію з context_processors
                    # Конвертуємо суму USD з урахуванням комісії в UAH
                    self.converted_amount_uah = usd_with_commission * decimal.Decimal(private_bank_rate)
                else:
                    self.converted_amount_uah = None  # Якщо немає суми, скидаємо конвертовану суму

            elif self.withdraw_type == 'fixed_15_30': # Оновлено
                if today_date.day <= 15:
                    self.scheduled_withdrawal_date = today_date.replace(day=15)
                elif today_date.day <= 30:
                    target_day = 30
                    last_day_of_current_month = calendar.monthrange(today_date.year, today_date.month)[1]
                    self.scheduled_withdrawal_date = datetime.date(today_date.year, today_date.month,
                                                                   min(target_day, last_day_of_current_month))
                else:
                    year = today_date.year
                    month = today_date.month + 1
                    if month > 12:
                        month = 1
                        year += 1
                    self.scheduled_withdrawal_date = datetime.date(year, month, 15)
            else:
                self.scheduled_withdrawal_date = None  # На всякий випадок, хоча всі варіанти покриті

        super().save(*args, **kwargs)
