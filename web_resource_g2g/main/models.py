# models.py
from django.db import models
from django.contrib.auth.models import User

from datetime import datetime

from django.utils import timezone


class Commission(models.Model):
    commission = models.IntegerField(default=0)
    created_time = models.DateTimeField(default=timezone.now)


class Sellers(models.Model):
    id_telegram = models.CharField(max_length=255, blank=True, null=True)
    auth_user = models.ForeignKey(User, on_delete=models.CASCADE)
    balance = models.IntegerField(default=0)
    interest_rate = models.IntegerField(default=75, blank=True, null=True)

    class Meta:
        db_table = 'sellers'

    def __str__(self):
        return f"seller: {self.auth_user}, telegram: {self.id_telegram}, balance: {self.balance}"


class PaymentHistory(models.Model):
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    amount = models.IntegerField(default=0)  # Сума виплати
    created_time = models.DateTimeField(default=timezone.now)  # Час виплати
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'payment_history'


class ServerUrls(models.Model):
    server_name = models.CharField(max_length=255)
    game_name = models.CharField(max_length=255)
    server_url = models.URLField()
    region = models.CharField(max_length=255)
    fraction = models.CharField(max_length=255)

    class Meta:
        db_table = 'server_urls'


class TopPrices(models.Model):
    server_name = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    top1 = models.IntegerField()
    top5 = models.IntegerField()
    top10 = models.IntegerField()
    top20 = models.IntegerField()
    mean10 = models.IntegerField()
    mean20 = models.IntegerField()
    minimal = models.IntegerField()
    mean10_lot = models.IntegerField()
    mean20_lot = models.IntegerField()
    double_minimal = models.IntegerField()
    created_time = models.TimeField(default=timezone.now)

    class Meta:
        db_table = 'top_prices'


class OffersForPlacement(models.Model):
    sellers = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    server_urls = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    currency = models.CharField(max_length=255)
    description = models.TextField()
    price = models.TextField(max_length=255)
    stock = models.IntegerField()
    min_units_per_order = models.IntegerField()
    active_rate = models.BooleanField(default=False)
    percent_offset = models.IntegerField()
    duration = models.IntegerField()
    face_to_face_trade = models.BooleanField(default=True)
    mail_delivery = models.BooleanField(default=True)
    auction_house = models.BooleanField(default=True)
    delivery_online_hrs = models.IntegerField()
    delivery_offline_hrs = models.IntegerField()
    is_created_lot = models.BooleanField(default=False)
    reserve_stock = models.IntegerField(default=0)
    order_status = models.BooleanField(default=False, null=True)

    class Meta:
        db_table = 'offers_for_placement'


class SoldOrders(models.Model):
    server = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    status = models.CharField(max_length=255)
    bought_by = models.CharField(max_length=255)
    character_name = models.CharField(max_length=255)
    sold_order_number = models.IntegerField()
    quantity = models.IntegerField()
    sent_gold = models.IntegerField(null=True, db_default=0)
    price_unit = models.IntegerField()
    total_amount = models.IntegerField()
    comission_fee = models.IntegerField()
    earned_without_admins_commission = models.IntegerField(default=0)
    owner_commission = models.IntegerField(default=0)
    technical_commission = models.IntegerField(default=0)
    to_be_earned = models.IntegerField()
    trade_mode = models.CharField(max_length=255)
    created_time = models.DateTimeField(default=timezone.now)
    send_message = models.BooleanField(default=False)
    path_to_video = models.CharField(max_length=255, blank=True)
    download_video_status = models.BooleanField(default=False, null=True)
    send_video_status = models.BooleanField(default=False, null=True)
    charged_to_payment = models.BooleanField(default=False)
    paid_in_salary = models.BooleanField(default=False)

    class Meta:
        db_table = 'sold_orders'

    # def save(self, *args, **kwargs):
    #     # Якщо статус змінюється на 'completed', оновлюємо баланс продавця
    #     if self.status == 'completed':
    #         seller = self.seller
    #         seller.balance += self.to_be_earned
    #         seller.save()
    #     super().save(*args, **kwargs)

