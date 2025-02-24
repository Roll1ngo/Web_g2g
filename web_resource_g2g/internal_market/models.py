from django.db import models
from django.utils import timezone

from main import models as main_models


class InternalOrder(models.Model):
    server = models.ForeignKey(main_models.ServerUrls, on_delete=models.CASCADE)
    internal_seller = models.ForeignKey(main_models.Sellers, on_delete=models.CASCADE)
    internal_buyer = models.ForeignKey(main_models.Sellers, on_delete=models.CASCADE,
                                       null=True, blank=True, related_name='internal_buyer')
    status = models.CharField(max_length=255, default='DELIVERING')
    character_name = models.CharField(max_length=255)
    sold_order_number = models.BigIntegerField(unique=True)
    quantity = models.IntegerField()
    sent_gold = models.IntegerField(null=True, blank=True, db_default=0)
    price_unit = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    earned_without_admins_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    owner_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    technical_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    trade_mode = models.CharField(max_length=255)
    created_time = models.DateTimeField(default=timezone.now)
    send_message = models.BooleanField(default=False)
    path_to_video = models.CharField(max_length=255, blank=True, default='')
    download_video_status = models.BooleanField(default=False, null=True)
    charged_to_payment = models.BooleanField(default=False)
    paid_in_salary = models.BooleanField(default=False)
    paid_to_owner = models.BooleanField(default=False)
    paid_to_technical = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.internal_seller.auth_user.username} №{self.sold_order_number} - {self.total_amount}$"

    def save(self, *args, **kwargs):
        if not self.sold_order_number:
            now = timezone.now()
            # Форматуємо дату та час у потрібний формат: ддммррггххссмм
            self.sold_order_number = int(now.strftime('%d%m%H%M%S%f')[:-4])
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Внутрішнє замовлення"
        verbose_name_plural = "Внутрішні замовлення"
