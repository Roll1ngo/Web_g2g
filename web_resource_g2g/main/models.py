# models.py
from django.db import models
from datetime import datetime

from django.utils import timezone


class Sellers(models.Model):
    id_discord = models.CharField(max_length=255)
    name_on_server = models.CharField(max_length=255)

    class Meta:
        db_table = 'sellers'

    def __str__(self):
        return self.name_on_server


class ServerUrls(models.Model):
    server_name = models.CharField(max_length=255)
    game_name = models.CharField(max_length=255)
    server_url = models.URLField()
    region = models.CharField(max_length=255)
    fraction = models.CharField(max_length=255)

    class Meta:
        db_table = 'server_urls'

    def __str__(self):
        return self.server_name


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

    def __str__(self):
        return f"TopPrices for {self.server_name}"


class OffersForPlacement(models.Model):
    sellers = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    server_urls = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    currency = models.IntegerField()
    description = models.TextField()
    price = models.CharField(max_length=255)
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

    class Meta:
        db_table = 'offers_for_placement'

    def __str__(self):
        return f"Offer by {self.sellers} on {self.server_urls}"