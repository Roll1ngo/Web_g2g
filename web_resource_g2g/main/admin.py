import asyncio
import datetime
import os
import sys
import time
from decimal import Decimal

from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import models
from django.shortcuts import redirect
from django.templatetags.static import static
from django.utils import timezone
from django.utils.html import format_html
from import_export.admin import ExportActionModelAdmin
from import_export import resources

from .crud import update_seller_balance, update_technical_balance, update_owner_balance
from .models import Sellers, SoldOrders, SellerServerInterestRate, ServerUrls, ChangeStockHistory, OffersForPlacement, \
    Commission
from .utils.logger_config import logger
from .tg_bot_run import send_messages_sync


@admin.register(ServerUrls)
class ServerUrlsAdmin(admin.ModelAdmin):
    list_display = ('server_name',)
    search_fields = ('server_name',)


@admin.register(ChangeStockHistory)
class ChangeStockHistoryAdmin(admin.ModelAdmin):
    # Поля для відображення у списку
    list_display = (
        "seller", "server", "stock",
        "active_rate_record", "created_time",
        "description"
    )

    # Фільтрація за цими полями
    list_filter = ("seller", "active_rate_record", "created_time")

    # Сортування за замовчуванням
    ordering = ('-created_time',)


class SellersResource(resources.ModelResource):
    class Meta:
        model = Sellers
        fields = ('auth_user__username', 'auth_user__email', 'balance')  # Поля для експорту


@admin.register(Sellers)
class SellersAdmin(ExportActionModelAdmin):
    resource_class = SellersResource
    list_display = ('auth_user', 'get_user_email', 'balance')
    actions = ['export_as_txt']  # Додаємо власну дію до списку дій

    def get_user_email(self, obj):
        return obj.auth_user.email

    get_user_email.short_description = 'Payoneer'


class SellerBalanceFilter(SimpleListFilter):
    title = 'Баланс продавця'
    parameter_name = 'seller_balance'

    def lookups(self, request, model_admin):
        return [
            ('<100', 'Менше 100'),
            ('100-500', 'Від 100 до 500'),
            ('>500', 'Більше 500'),
        ]

    def queryset(self, request, queryset):
        if self.value() == '<100':
            return queryset.filter(seller__balance__lt=100)
        elif self.value() == '100-500':
            return queryset.filter(seller__balance__gte=100, seller__balance__lte=500)
        elif self.value() == '>500':
            return queryset.filter(seller__balance__gt=500)
        return queryset


class CreatedTimeFilter(admin.SimpleListFilter):
    title = 'Час створення'  # Назва фільтра, що відображається в адмін-панелі
    parameter_name = 'created_time'  # Ім'я параметра, що передається в URL

    def lookups(self, request, model_admin):
        return (
            ('last_30_days', 'Останні 30 днів'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'last_30_days':
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            return queryset.filter(created_time__gte=thirty_days_ago)
        elif self.value() == 'all':
            return queryset
        return queryset  # Повертаємо початковий queryset, якщо фільтр не застосовано


@admin.register(SoldOrders)
class SoldOrdersAdmin(admin.ModelAdmin):
    # Поля для відображення у списку
    list_display = (
        'seller_name',
        'seller_balance',
        'order_value',
        'created_time',
        'charged_to_payment_icon',
        'paid_in_salary_icon',
        'owner_commission',
        'paid_to_owner',
        'technical_commission',
        'paid_to_technical',
    )

    # Фільтрація за цими полями
    list_filter = ('seller__auth_user__username',
                   ('paid_in_salary', admin.BooleanFieldListFilter),
                   ('charged_to_payment', admin.BooleanFieldListFilter),
                   ('paid_to_technical', admin.BooleanFieldListFilter),
                   ('paid_to_owner', admin.BooleanFieldListFilter),
                   CreatedTimeFilter,
                   SellerBalanceFilter)

    # Сортування за замовчуванням
    ordering = ('-created_time',)

    # Вказуємо список доступних дій
    actions = ['mark_paid', 'pay_technical_commission', 'mark_reviewed', 'send_message_to_seller']

    # Заборона створення нових замовлень
    def has_add_permission(self, request):
        return False

    # Метод для відображення імені продавця
    def seller_name(self, obj):
        return obj.seller.auth_user.username

    seller_name.admin_order_field = 'seller__auth_user__username'
    seller_name.short_description = 'Продавець'

    # Метод для відображення балансу продавця
    def seller_balance(self, obj):
        return obj.seller.balance

    seller_balance.admin_order_field = 'seller__balance'
    seller_balance.short_description = 'Баланс'

    def get_queryset(self, request):
        # Додаткові оптимізації для зменшення кількості запитів до БД
        queryset = super().get_queryset(request)
        return queryset.select_related('seller')

    def seller(self, obj):
        return obj.seller.auth_user.username

    seller.admin_order_field = 'seller__auth_user__username'
    seller.short_description = 'Продавець'

    @admin.action(description='Відмітити як оплачені')
    def mark_paid(self, request, queryset):

        # Отримуємо список унікальних продавців з оновлених замовлень
        sellers_ids = set(queryset.values_list('seller_id', flat=True).distinct())
        logger.info(f"sellers_ids__{sellers_ids}")

        # Оновлюємо всі записи, які відповідають фільтрації
        updated_count = queryset.update(paid_in_salary=True)

        # Виключаємо продавців з ID 1 та 2
        excluded_sellers = {1, 2}

        for seller_id in sellers_ids:
            logger.info(seller_id)
            logger.info(f"seller_id__{seller_id}")
            if seller_id not in excluded_sellers:
                update_seller_balance(seller_id)

        self.message_user(
            request,
            f"Успішно оновлено {updated_count} записів, встановлено paid_in_salary=True."
        )

    @admin.action(description='Сплатити технічну комісію')
    def pay_technical_commission(self, request, queryset):
        updated_count = queryset.update(paid_to_technical=True)
        update_technical_balance()  # Виклик celery task
        self.message_user(request, f"Оновлено записів: {updated_count}."
                                   f" Встановлено статус 'оплачено технічну комісію'.")

    @admin.action(description='Відмітити як переглянуто')
    def mark_reviewed(self, request, queryset):
        updated_count = queryset.update(paid_to_owner=True)
        for order in queryset:  # Ітерація по оновленим об'єктам
            update_owner_balance()
        self.message_user(request, f"Успішно оновлено {updated_count} записів, відмічено як переглянуті.")

    def order_value(self, obj):
        return obj.earned_without_admins_commission

    order_value.short_description = 'Вартість замовлення'

    def _icon(self, obj, field_name):  # Створення функції для відображення іконок
        if getattr(obj, field_name):
            icon_url = static('admin/img/icon-yes.svg')
        else:
            icon_url = static('admin/img/icon-no.svg')
        return format_html('<img src="{}" alt="{}">', icon_url, getattr(obj, field_name))

    def charged_to_payment_icon(self, obj):
        return self._icon(obj, 'charged_to_payment')

    charged_to_payment_icon.short_description = 'До оплати'

    def paid_in_salary_icon(self, obj):
        return self._icon(obj, 'paid_in_salary')

    paid_in_salary_icon.short_description = 'Оплачено'

    def paid_to_technical_icon(self, obj):  # Функція для відображення іконки paid_to_technical
        return self._icon(obj, 'paid_to_technical')

    paid_to_technical_icon.short_description = 'Технічна комісія сплачена'

    def paid_to_owner_icon(self, obj):  # Функція для відображення іконки paid_to_owner
        return self._icon(obj, 'paid_to_owner')


    paid_to_owner_icon.short_description = 'Власнику сплачено'


class ServerUrlsChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.server_name} - {obj.game_name}"


@admin.register(SellerServerInterestRate)
class SellerServerInterestRateAdmin(admin.ModelAdmin):
    list_display = ('seller', 'server_display', 'interest_rate')
    list_filter = ('seller', 'server__game_name', 'server__server_name')
    list_editable = ('interest_rate',)
    search_fields = ('seller__name', 'server__game_name', 'server__server_name')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "server":
            # Sort the queryset by server_name alphabetically
            kwargs["queryset"] = ServerUrls.objects.all().order_by('server_name')
            kwargs["form_class"] = ServerUrlsChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def server_display(self, obj):
        return f"{obj.server.server_name} - {obj.server.game_name}"

    server_display.short_description = 'Server'


@admin.register(OffersForPlacement)
class OffersForPlacementAdmin(admin.ModelAdmin):
    list_display = ('sellers', 'server_urls', 'active_rate', 'price', 'stock', 'face_to_face_trade', 'order_status')
    list_editable = ('order_status', 'active_rate', 'face_to_face_trade')
    list_filter = ('sellers',)
    search_fields = ('sellers__name', 'currency', 'description')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('sellers', 'server_urls')


class AddOrder(SoldOrders):
    class Meta:
        proxy = True
        verbose_name = "Замовлення"
        verbose_name_plural = "Замовлення"


class AddOrderForm(forms.ModelForm):
    TRADE_MODE_CHOICES = [
        ("Mail", "Mail"),
        ("Face to face trade", "Face to face trade"),
    ]

    price_unit = forms.DecimalField(
        label="Ціна за одиницю",
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'readonly': 'readonly'})
    )

    earned_without_admins_commission = forms.DecimalField(
        label="Чистий заробіток без сервісної комісії",
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'readonly': 'readonly'})
    )

    owner_commission = forms.DecimalField(
        label="Комісія власника",
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'readonly': 'readonly'})
    )

    technical_commission = forms.DecimalField(
        label="Технічна комісія",
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'readonly': 'readonly'})
    )

    trade_mode = forms.ChoiceField(
        choices=TRADE_MODE_CHOICES,
        label="Режим торгівлі",
        widget=forms.Select()
    )

    class Meta:
        model = AddOrder
        fields = '__all__'  # Всі поля з моделі


@admin.register(AddOrder)
class AddOrderAdmin(admin.ModelAdmin):
    technical_commission_percent = Decimal(5)  # Перетворюємо в Decimal

    form = AddOrderForm  # Використовуємо кастомну форму
    list_display = (
        'server',
        'seller',
        'status',
        'character_name',
        'sold_order_number',
        'quantity',
        'trade_mode',
        'created_time',
        'total_amount',
        'owner_commission',
        'technical_commission',
        'earned_without_admins_commission',
        'to_be_earned',
        'sent_gold',
        'bought_by',
        'price_unit',
        'comission_fee',  # Note the correct spelling: commission_fee
        'send_message',
        'path_to_video',
        'download_video_status',
        'send_video_status',
        'charged_to_payment',
        'paid_in_salary',
        'paid_to_owner',
        'paid_to_technical',
    )
    list_filter = ('seller', 'created_time')
    actions = ['send_message_to_seller']

    # Поля для відображення у формі створення замовлення
    fields = (
        'seller',
        'server',
        'character_name',
        'sold_order_number',
        'quantity',
        'trade_mode',
        'total_amount',
        'created_time'
    )
    readonly_fields = ('price_unit', 'earned_without_admins_commission', 'owner_commission', 'technical_commission')

    search_fields = ('server__name',)
    # Додаємо поле server до autocomplete_fields
    autocomplete_fields = ['server']

    # Дозволяємо створення нових замовлень
    def has_add_permission(self, request):
        return True

    @admin.action(description='Надіслати повідомлення продавцю')
    def send_message_to_seller(self, request, queryset):
        for order in queryset:
            seller = order.seller
            if seller.id_telegram:  # Перевіряємо, чи є у продавця Telegram ID
                message = str(f"Вітаю, {seller.auth_user.username} для вас замовлення від {order.created_time} \n"
                              f"Сервер___________{order.server.server_name}\n"
                              f"Гра___________{order.server.game_name}\n"
                              f"Кількість___________{order.quantity}\n"
                              f"Ім'я персонажа___________{order.character_name}\n"
                              f"Спосіб доставки___________{order.trade_mode}\n"
                              f"Сума замовлення: {order.earned_without_admins_commission}\n"
                              )
                logger.info(message)

                send_messages_sync(seller.id_telegram, seller.auth_user.username, message)

            else:
                self.message_user(request, f"У продавця {seller.auth_user.username} немає Telegram ID.",
                                  level='WARNING')


    # Встановлення значень за замовчанням для полів
    def save_model(self, request, obj, form, change):

        # Отримуємо exchange_commission (з останнього запису в таблиці Commission)
        exchange_commission = Commission.objects.order_by('-created_time').first()
        exchange_commission = Decimal(exchange_commission.commission) if exchange_commission else Decimal(0)

        # Отримуємо seller_interest_rate для вказаного продавця та сервера
        try:
            seller_interest = SellerServerInterestRate.objects.get(seller=obj.seller, server=obj.server)
            seller_interest_rate = Decimal(seller_interest.interest_rate)
        except SellerServerInterestRate.DoesNotExist:
            seller_interest_rate = Decimal(0)  # Якщо немає ставки
            logger.critical(f"Ставка не знайдена для продавця {obj.seller} та сервера {obj.server}")

        total_amount = Decimal(obj.total_amount)  # Перетворюємо в Decimal

        # Обчислюємо значення за формулами
        to_be_earned_without_exchange_commission = total_amount * (Decimal(1) - exchange_commission / Decimal(100))
        earned_without_service_commission = to_be_earned_without_exchange_commission * (
                    seller_interest_rate / Decimal(100))
        full_service_commission = to_be_earned_without_exchange_commission - earned_without_service_commission
        technical_commission = to_be_earned_without_exchange_commission * (
                    Decimal(self.technical_commission_percent) / Decimal(100))
        owner_commission = full_service_commission - technical_commission

        # Заповнюємо приховані поля значеннями за замовчанням
        if not change:  # Перевіряємо, що це створення нового об'єкта
            obj.charged_to_payment = False
            obj.paid_in_salary = False
            obj.paid_to_owner = False
            obj.paid_to_technical = False
            obj.bought_by = 'Vlad_Handle_order'
            obj.send_message = True
            obj.path_to_video = ''
            obj.download_video_status = False
            obj.send_video_status = False
            obj.status = 'DELIVERING'
            obj.sent_gold = 0
            obj.to_be_earned = to_be_earned_without_exchange_commission
            obj.earned_without_admins_commission = earned_without_service_commission
            obj.technical_commission = technical_commission
            obj.owner_commission = owner_commission
            obj.price_unit = obj.earned_without_admins_commission / obj.quantity if obj.quantity else 0

        # Вивід результатів перед збереженням
        logger.warning(f"Загальна вартість: {obj.total_amount}")
        logger.warning(f"Ставка {obj.seller.auth_user.username} на сервері {obj.server.server_name}: {seller_interest_rate}")
        logger.warning(f"З вирахуванням  комісії біржі: {obj.to_be_earned}")
        logger.warning(f"З вирахуванням адміністративної комісії: {obj.earned_without_admins_commission}")
        logger.warning(f"Комісія власника: {obj.owner_commission}")
        logger.warning(f"Технічна комісія: {obj.technical_commission}")
        logger.warning(f"Ціна за одиницю з урахуванням усіх комісій: {obj.price_unit}")

        # Зберігаємо об'єкт
        super().save_model(request, obj, form, change)
