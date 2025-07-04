from django.conf import settings
from django.db import models

# Create your models here.
class WithdrawalArchive(models.Model):
    """
    Модель для зберігання запитів на виведення коштів користувачами та
    архівування інформації про здійснені виплати.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests',
        verbose_name="Користувач",
        unique=False # Changed to False, as a user might have multiple archived withdrawals
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сума виведення",
        null=True,
        blank=True
    )

    WITHDRAW_TYPE_CHOICES = [
        ('fixed_15_30', '15 і 30 числа кожного місяця (вивести всю суму)'),
        ('custom', 'Терміновий вивід (протягом 24 годин)'),
        ('do_not_withdraw', 'Не виводити'),
    ]
    withdraw_type = models.CharField(
        max_length=30,
        choices=WITHDRAW_TYPE_CHOICES,
        default='fixed_15_30',
        verbose_name="Тип виведення"
    )

    PAYMENT_METHOD_CHOICES = [
        ('payoneer', 'Payoneer'),
        ('visa_mastercard', 'Visa / Mastercard (грн)'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='payoneer',
        verbose_name="Метод виведення",
        null=True,
        blank=True
    )

    commission_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        verbose_name="Комісія (%)",
        null=True,
        blank=True
    )

    withdrawal_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата виведення"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата створення"
    )

    payment_details = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Деталі оплати"
    )

    archived_sold_order_ids = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Архівні ID проданих замовлень"
    )
    archived_internal_order_ids = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Архівні ID внутрішніх замовлень"
    )
    archived_commission_breakdown_ids = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Архівні ID розбивки комісій"
    )

    def __str__(self):
        return f"Запит на виведення для {self.user.username} - {self.amount} {self.withdraw_type}"