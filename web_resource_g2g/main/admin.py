import datetime

from decimal import Decimal

from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.shortcuts import redirect

from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from import_export.admin import ExportActionModelAdmin
from import_export import resources

from . import crud
from .models import Sellers, SoldOrders, SellerServerInterestRate, ServerUrls, ChangeStockHistory, OffersForPlacement, \
    CommissionBreakdown, CommissionRates, VitaliyOrders
from .utils.logger_config import logger
from .tg_bot_run import send_messages_sync


class CreatedTimeFilter(admin.SimpleListFilter):
    title = 'Час створення'  # Назва фільтра, що відображається в адмін-панелі
    parameter_name = 'created_time'  # Ім'я параметра, що передається в URL

    def lookups(self, request, model_admin):
        return (
            ('last_24_hours', 'За добу'),
            ('last_3_days', 'За 3 дні'),
            ('last_7_days', 'За 7 днів'),
            ('last_15_days', 'За 15 днів'),
            ('last_30_days', 'За місяць')

        )

    def queryset(self, request, queryset):
        if self.value() == 'last_24_hours':
            twenty_four_hours_ago = timezone.now() - datetime.timedelta(hours=24)
            return queryset.filter(created_time__gte=twenty_four_hours_ago)
        elif self.value() == 'last_3_days':
            three_days_ago = timezone.now() - datetime.timedelta(days=3)
            return queryset.filter(created_time__gte=three_days_ago)
        elif self.value() == 'last_7_days':
            seven_days_ago = timezone.now() - datetime.timedelta(days=7)
            return queryset.filter(created_time__gte=seven_days_ago)
        elif self.value() == 'last_10_days':
            fifteen_days_ago = timezone.now() - datetime.timedelta(days=15)
            return queryset.filter(created_time__gte=fifteen_days_ago)
        elif self.value() == 'last_30_days':
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            return queryset.filter(created_time__gte=thirty_days_ago)

        return queryset  # Повертаємо початковий queryset, якщо фільтр не застосовано


@admin.register(VitaliyOrders)
class VitaliyOrdersAdmin(admin.ModelAdmin):
    list_display = ('status', 'sold_order_number', 'created_time')
    list_filter = (CreatedTimeFilter, 'status')
    ordering = ('created_time',)


@admin.register(CommissionBreakdown)
class CommissionBreakdownAdmin(admin.ModelAdmin):
    list_display = ('order', 'seller', 'service_type', 'amount', 'created_time',
                    'charged_to_payment_commission', 'paid_in_salary_commission')
    list_filter = ('seller', 'service_type', 'charged_to_payment_commission',
                   'paid_in_salary_commission', CreatedTimeFilter)

    actions = ['mark_paid']

    @admin.action(description='Відмітити комісії як оплачені')
    def mark_paid(self, request, queryset):

        # Оновлюємо всі записи, які відповідають фільтрації
        queryset.update(paid_in_salary_commission=True)
        crud.update_owner_balance()

        # Отримуємо список унікальних продавців з оновлених замовлень
        users_ids = set(queryset.values_list('seller__auth_user_id', flat=True).distinct())

        for user_id in users_ids:
            crud.update_seller_balance(user_id)


@admin.register(CommissionRates)
class CommissionRatesAdmin(admin.ModelAdmin):
    list_display = ('exchange', 'renter_lvl1', 'renter_lvl2',
                    'mentor', 'owner', 'technical', 'recruiter', 'edit_link')  # Add a column for the link

    fields = ('exchange', 'renter', 'mentor', 'owner', 'technical', 'recruiter')

    def edit_link(self, obj):
        return format_html('<a href="{}">Редагувати</a>',
                           reverse('admin:main_commissionrates_change', args=[obj.pk]))
    edit_link.allow_tags = True  # Mark the function as safe for rendering HTML
    edit_link.short_description = ' '  # Set a blank column header

    # Optional: If you want to customize the change form URL
    def get_changeform_url(self, obj=None):
        if obj is not None:
            return reverse('admin:main_commissionrates_change', args=[obj.pk])
        else:
            return super().get_changeform_url(obj)


@admin.register(ServerUrls)
class ServerUrlsAdmin(admin.ModelAdmin):
    list_display = ('server_name',)
    search_fields = ('server_name', 'game_name')
    ordering = ('server_name',)

    def has_module_permission(self, request):
        """Приховуємо модель із головної сторінки Django Admin"""
        return False


@admin.register(ChangeStockHistory)
class ChangeStockHistoryAdmin(admin.ModelAdmin):
    # Поля для відображення у списку
    list_display = (
        "seller", "server", "stock",
        "active_rate_record", "created_time",
        "description"
    )

    # Фільтрація за цими полями
    list_filter = ("seller", "active_rate_record", "created_time", "description")

    # Сортування за замовчуванням
    ordering = ('-created_time',)


class SellersResource(resources.ModelResource):
    class Meta:
        model = Sellers
        fields = ('auth_user__username', 'auth_user__email', 'balance')  # Поля для експорту


@admin.register(Sellers)
class SellersAdmin(ExportActionModelAdmin):
    resource_class = SellersResource
    list_display = ('auth_user', 'get_user_email',
                    'mentor', 'recruiter', 'balance')

    list_editable = ('mentor', 'recruiter')

    actions = ['export_as_txt', 'update_balance']  # Додаємо власну дію до списку дій

    @admin.action(description='Оновити баланс')
    def update_balance(self, request, queryset):

        for user_id in queryset.values_list('auth_user_id', flat=True).distinct():
            new_balance = crud.get_balance(user_id)
            logger.info(f"Оновлено баланс для продавця {user_id}: {new_balance}")
        crud.update_technical_balance()
        crud.update_owner_balance()
        self.message_user(request, f"Баланс оновлено для {queryset.count()} замовлень.")

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
    actions = ['update_balance',
               'mark_paid',
               'pay_technical_commission',
               'mark_reviewed',
               'send_message_to_seller']

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

    @admin.action(description='Оновити баланс')
    def update_balance(self, request, queryset):

        for user_id in queryset.values_list('seller__auth_user_id__id', flat=True).distinct():
            new_balance = crud.get_balance(user_id)
            logger.info(f"Оновлено баланс для продавця {user_id}: {new_balance}")
        crud.update_technical_balance()
        crud.update_owner_balance()
        self.message_user(request, f"Баланс оновлено для {queryset.count()} замовлень.")

    @admin.action(description='Відмітити як оплачені')
    def mark_paid(self, request, queryset):

        # Отримуємо список унікальних продавців з оновлених замовлень
        users_ids = set(queryset.values_list('seller__auth_user_id__id', flat=True).distinct())
        logger.info(f"auth_user_id{users_ids}")

        # Оновлюємо всі записи, які відповідають фільтрації
        updated_count = queryset.update(paid_in_salary=True)

        # Виключаємо продавців з ID 1 та 2
        excluded_sellers = {1, 2}

        for user_id in users_ids:
            logger.info(user_id)
            logger.info(f"seller_id__{user_id}")
            if user_id not in excluded_sellers:
                crud.update_status_paid_in_salary_commission(user_id)
                crud.update_seller_balance(user_id)

        self.message_user(
            request,
            f"Успішно оновлено {updated_count} записів, встановлено paid_in_salary=True."
        )

    @admin.action(description='Сплатити технічну комісію')
    def pay_technical_commission(self, request, queryset):
        updated_count = queryset.update(paid_to_technical=True)
        crud.update_technical_balance()  # Виклик celery task
        self.message_user(request, f"Оновлено записів: {updated_count}."
                                   f" Встановлено статус 'оплачено технічну комісію'.")

    @admin.action(description='Відмітити як переглянуто')
    def mark_reviewed(self, request, queryset):
        updated_count = queryset.update(paid_to_owner=True)
        for order in queryset:  # Ітерація по оновленим об'єктам
            crud.update_owner_balance()
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
    list_display = ('seller', 'server_display',
                    'interest_rate',
                    'renter_lvl1', 'renter_lvl2')
    list_filter = ('seller', 'server__game_name')
    list_editable = ('interest_rate', 'renter_lvl1', 'renter_lvl2')
    search_fields = ('seller__auth_user__username', 'server__server_name', 'server__game_name')
    # Додаємо autocomplete для server
    autocomplete_fields = ['server']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        for obj in queryset:
            new_rate = crud.calculate_seller_total_rate(obj.seller.id, obj.server.id)
            if obj.interest_rate != new_rate:
                obj.interest_rate = new_rate
                obj.save(update_fields=['interest_rate'])  # Оновлюємо лише interest_rate
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "server":
            kwargs["queryset"] = ServerUrls.objects.all().order_by('server_name')
            kwargs["form_class"] = ServerUrlsChoiceField
        elif db_field.name in ('renter_lvl1', 'renter_lvl2'):
            # Отримуємо унікальні екземпляри Sellers, а не User
            kwargs["queryset"] = Sellers.objects.order_by('auth_user__username').distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def server_display(self, obj):
        return f"{obj.server.server_name} - {obj.server.game_name}"

    server_display.short_description = 'Server'


# Форма для встановлення значень за замовчуванням
class OffersForPlacementForm(forms.ModelForm):
    price_choices = [
        ("minimal", "Швидко"),
        ("mean10_lot", "Баланс"),
        ("mean20_lot", "Дорого"),
    ]

    price = forms.ChoiceField(choices=price_choices, required=True)

    class Meta:
        model = OffersForPlacement
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Встановлюємо значення за замовчуванням
        self.fields['currency'].initial = "USD"
        self.fields['description'].initial = "gold"
        self.fields['min_units_per_order'].initial = 1
        self.fields['duration'].initial = 3
        self.fields['auction_house'].initial = False
        self.fields['percent_offset'].initial = 0
        self.fields['delivery_online_hrs'].initial = 18
        self.fields['delivery_offline_hrs'].initial = 6
        self.fields['double_minimal_mode_status'].initial = False
        self.fields['reserve_stock'].initial = 0


@admin.register(OffersForPlacement)
class OffersForPlacementAdmin(admin.ModelAdmin):
    form = OffersForPlacementForm  # Використовуємо кастомну форму

    list_display = ('sellers', 'server_urls', 'active_rate',
                    'price', 'stock', 'face_to_face_trade', 'order_status', 'double_minimal_mode_status')
    list_editable = ('order_status', 'active_rate', 'face_to_face_trade', 'double_minimal_mode_status')
    list_filter = ('sellers', 'active_rate', 'order_status', 'double_minimal_mode_status')
    search_fields = ('sellers__name', 'currency', 'description', 'server__server_name', 'server__game_name')
    autocomplete_fields = ['server_urls']

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
    STATUS_CHOICES = [('DELIVERING', 'DELIVERING'),
                      ('DELIVERED', 'DELIVERED'),
                      ('COMPLETED', 'COMPLETED'),
                      ('NOTFOUNDONG2G', 'NOTFOUNDONG2G'),
                      ('CANCELLED', 'CANCELLED'),
                      ('CANCEL_REQUESTED', 'CANCEL_REQUESTED'),]

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
        label="Trade mode",
        widget=forms.Select()
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        label="Status",
        widget=forms.Select()
    )

    class Meta:
        model = AddOrder
        fields = '__all__'  # Всі поля з моделі


@admin.register(AddOrder)
class AddOrderAdmin(admin.ModelAdmin):

    form = AddOrderForm  # Використовуємо кастомну форму
    list_display = (
        'id',
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
        'send_message_to_buyer_status',
        'path_to_video',
        'download_video_status',
        'send_video_status',
        'charged_to_payment',
        'paid_in_salary',
        'paid_to_owner',
        'paid_to_technical',
    )
    list_filter = ('seller', CreatedTimeFilter, 'paid_in_salary', 'status', 'download_video_status')
    actions = ['send_message_to_seller']

    # Поля для відображення у формі створення замовлення
    add_fields = (
        'seller',
        'server',
        'character_name',
        'sold_order_number',
        'quantity',
        'trade_mode',
        'total_amount',
        'created_time'
    )
    # Всі поля доступні для редагування
    fields = (
        'server',
        'seller',
        'status',
        'character_name',
        'sold_order_number',
        'quantity',
        'trade_mode',
        'total_amount',
        'created_time',
        'sent_gold',
        'bought_by',
        'send_message',
        'send_message_to_buyer_status',
        'path_to_video',
        'download_video_status',
        'send_video_status',
        'charged_to_payment',
        'paid_in_salary',
        'paid_to_owner',
        'paid_to_technical',
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

                response = send_messages_sync(seller.id_telegram, seller.auth_user.username, message)
                if response:
                    SoldOrders.objects.filter(sold_order_number=order.sold_order_number).update(send_message=True)
                    OffersForPlacement.objects.filter(sellers=seller.id,
                                                      server_urls=order.server.id).update(order_status=True)
                else:
                    "Telegram повідомлення не надіслано"

            else:
                self.message_user(request, f"У продавця {seller.auth_user.username} немає Telegram ID.",
                                  level='WARNING')

    # Встановлення значень за замовчанням для полів
    def save_model(self, request, obj, form, change):

        # Отримуємо exchange_commission (з останнього запису в таблиці Commission)
        global_commissions_rates = crud.get_global_commissions_rates()
        exchange_commission = Decimal(global_commissions_rates['exchange'])
        technical_commission = Decimal(global_commissions_rates['technical'])
        owner_commission = Decimal(global_commissions_rates['owner'])

        seller_id = obj.seller.id
        server_id = obj.server.id
        order_number = obj.sold_order_number
        # Отримуємо seller_interest_rate для вказаного продавця та сервера
        try:
            seller_interest = SellerServerInterestRate.objects.get(seller=seller_id, server=server_id)
            seller_interest_rate = Decimal(seller_interest.interest_rate)
        except SellerServerInterestRate.DoesNotExist:
            seller_interest_rate = Decimal(0)  # Якщо немає ставки
            logger.critical(f"Ставка не знайдена для продавця {obj.seller} та сервера {obj.server}")

        total_amount = Decimal(obj.total_amount)  # Перетворюємо в Decimal

        # Обчислюємо значення за формулами
        to_be_earned_without_exchange_commission = total_amount * (Decimal(1) - exchange_commission / Decimal(100))
        earned_without_service_commission = to_be_earned_without_exchange_commission * (
                    seller_interest_rate / Decimal(100))
        technical_commission = to_be_earned_without_exchange_commission * (
                    technical_commission / Decimal(100))
        owner_commission = to_be_earned_without_exchange_commission * (
                    owner_commission / Decimal(100))

        # Заповнюємо приховані поля значеннями за замовчанням
        if not change:  # Перевіряємо, що це створення нового об'єкта
            obj.charged_to_payment = False
            obj.paid_in_salary = False
            obj.paid_to_owner = False
            obj.paid_to_technical = False
            obj.bought_by = 'Vlad_Handle_order'
            obj.send_message = True
            obj.send_message_to_buyer_status = False
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
        logger.warning(f"Ставка {obj.seller.auth_user.username}"
                       f" на сервері {obj.server.server_name}: {seller_interest_rate}")
        logger.warning(f"З вирахуванням  комісії біржі: {obj.to_be_earned}")
        logger.warning(f"З вирахуванням адміністративної комісії: {obj.earned_without_admins_commission}")
        logger.warning(f"Комісія власника: {obj.owner_commission}")
        logger.warning(f"Технічна комісія: {obj.technical_commission}")
        logger.warning(f"Ціна за одиницю з урахуванням усіх комісій: {obj.price_unit}")

        # Зберігаємо об'єкт
        super().save_model(request, obj, form, change)
        crud.calculate_and_record_mentor_renter_recruiter_commissions(seller_id, server_id,
                                                                      to_be_earned_without_exchange_commission,
                                                                      order_number)
