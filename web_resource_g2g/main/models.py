from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Commission(models.Model):
    commission = models.IntegerField(default=0)
    created_time = models.DateTimeField(default=timezone.now)


class Sellers(models.Model):
    id_telegram = models.CharField(max_length=255, blank=True, null=True)
    auth_user = models.ForeignKey(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    mentor = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="mentees")
    recruiter = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="recruits")

    class Meta:
        db_table = 'sellers'
        verbose_name_plural = "Продавці"
        verbose_name = "Продавця"

    def __str__(self):
        return self.auth_user.username


class ServerUrls(models.Model):
    server_name = models.CharField(max_length=255)
    game_name = models.CharField(max_length=255)
    server_url = models.URLField()
    region = models.CharField(max_length=255)
    fraction = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.server_name} - {self.game_name}"

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
    double_minimal_mode_status = models.BooleanField(default=False)
    reserve_stock = models.IntegerField(default=0)
    order_status = models.BooleanField(default=False, null=True)

    class Meta:
        db_table = 'offers_for_placement'
        verbose_name = "Пропозицію для розміщення на торгах"
        verbose_name_plural = "Пропозиції для розміщення на торгах"


class SoldOrders(models.Model):
    server = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    status = models.CharField(max_length=255)
    bought_by = models.CharField(max_length=255)
    character_name = models.CharField(max_length=255)
    sold_order_number = models.IntegerField()
    quantity = models.IntegerField()
    sent_gold = models.IntegerField(null=True, db_default=0)
    price_unit = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    comission_fee = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    earned_without_admins_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    owner_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    technical_commission = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    to_be_earned = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    trade_mode = models.CharField(max_length=255)
    created_time = models.DateTimeField(default=timezone.now)
    send_message = models.BooleanField(default=False)
    path_to_video = models.CharField(max_length=255, blank=True)
    download_video_status = models.BooleanField(default=False, null=True)
    send_video_status = models.BooleanField(default=False, null=True)
    send_message_to_buyer_status = models.BooleanField(default=False, null=True)
    charged_to_payment = models.BooleanField(default=False)
    paid_in_salary = models.BooleanField(default=False)
    paid_to_owner = models.BooleanField(default=False)
    paid_to_technical = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.seller.auth_user.username} №{self.sold_order_number} - {self.total_amount}$"

    class Meta:
        db_table = 'sold_orders'
        verbose_name = "Список замовлень для виплати"
        verbose_name_plural = "Список замовлень для виплати"  # Множина


class VitaliyOrders(models.Model):
    status = models.CharField(max_length=255, null=True, default="REGISTERED", blank=True)
    sold_order_number = models.IntegerField()
    created_time = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Замовлення Віталія"
        verbose_name_plural = "Замовлення Віталія"


class SellerServerInterestRate(models.Model):
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    server = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    interest_rate = models.IntegerField(null=False, validators=[
        MinValueValidator(1),
        MaxValueValidator(100)
    ])
    renter_lvl1 = models.ForeignKey(Sellers, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name="Renter 10%",
                                    related_name="sellers_renters_lvl1")
    renter_lvl2 = models.ForeignKey(Sellers, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name="Renter 5%",
                                    related_name="sellers_renters_lvl2")

    def __str__(self):
        return f"{self.seller}"

    class Meta:
        verbose_name_plural = "Сервера продавців з ставками"
        verbose_name = "Сервер продавця з ставкою"


class ChangeStockHistory(models.Model):
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE)
    server = models.ForeignKey(ServerUrls, on_delete=models.CASCADE)
    stock = models.IntegerField()
    active_rate_record = models.BooleanField(default=False)
    created_time = models.DateTimeField(default=timezone.now)  # Час виплати
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Рядок"
        verbose_name_plural = "Історія зміни стоку та статусу лотів"


class CommissionRates(models.Model):
    exchange = models.DecimalField(max_digits=5, decimal_places=3, default=0.07)  # Біржа
    renter_lvl1 = models.DecimalField(max_digits=5, decimal_places=3, default=0.05, verbose_name="Renter 10%")
    renter_lvl2 = models.DecimalField(max_digits=5, decimal_places=3, default=0.10, verbose_name="Renter 5%")  # Оренда персонажа
    mentor = models.DecimalField(max_digits=5, decimal_places=3, default=0.05)  # Ментор
    owner = models.DecimalField(max_digits=5, decimal_places=3, default=0.05)  # Власник
    technical = models.DecimalField(max_digits=5, decimal_places=3, default=0.05)  # Технічна підтримка
    recruiter = models.DecimalField(max_digits=5, decimal_places=3, default=0.05)  # Рекрутер

    def __str__(self):
        return "Ставки комісій"

    class Meta:
        verbose_name = "Ставка комісії"
        verbose_name_plural = "Ставки комісій"


class CommissionBreakdown(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    order = GenericForeignKey('content_type', 'object_id')
    seller = models.ForeignKey(Sellers, on_delete=models.CASCADE, related_name="commissions")
    service_type = models.CharField(max_length=255)  # Наприклад, "біржа", "оренда", "ментор"
    amount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    charged_to_payment_commission = models.BooleanField(default=False)
    paid_in_salary_commission = models.BooleanField(default=False)
    created_time = models.DateTimeField(default=timezone.now)


    class Meta:
        verbose_name = "Отримані комісії с замовлень"
        verbose_name_plural = "Отримані комісії с замовлень"
