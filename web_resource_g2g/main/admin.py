import datetime
import time

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.templatetags.static import static
from django.utils import timezone
from django.utils.html import format_html

from .crud import update_seller_balance, update_technical_balance, update_owner_balance
from .models import Sellers, SoldOrders
from .utils.logger_config import logger


@admin.register(Sellers)
class SellersAdmin(admin.ModelAdmin):
    list_display = ('auth_user', 'interest_rate', 'balance')  # замініть на поля вашої моделі
    list_editable = ('interest_rate',)  # поля, які можна редагувати прямо у списку


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
        return queryset # Повертаємо початковий queryset, якщо фільтр не застосовано


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
    actions = ['mark_paid', 'pay_technical_commission', 'mark_reviewed']

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
        update_technical_balance() # Виклик celery task
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

