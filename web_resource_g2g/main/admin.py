from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.templatetags.static import static
from django.utils.html import format_html

from .models import Sellers, SoldOrders


@admin.register(Sellers)
class SellersAdmin(admin.ModelAdmin):
    list_display = ('auth_user', 'interest_rate', 'balance')  # замініть на поля вашої моделі
    list_editable = ('balance', 'interest_rate')  # поля, які можна редагувати прямо у списку


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
        'paid_in_salary_icon'
            )

    # Фільтрація за цими полями
    list_filter = (('charged_to_payment', admin.BooleanFieldListFilter),
                   ('paid_in_salary', admin.BooleanFieldListFilter),
                   'created_time', 'seller', SellerBalanceFilter)

    # Сортування за замовчуванням
    ordering = ('-created_time',)

    # Вказуємо список доступних дій
    actions = ['mark_paid']

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
        # Оновлюємо всі записи, які відповідають фільтрації
        updated_count = queryset.update(paid_in_salary=True)
        self.message_user(
            request,
            f"Успішно оновлено {updated_count} записів, встановлено paid_in_salary=True."
        )
    # Метод для відображення значення earned_without_admins_commission з бажаною назвою

    def order_value(self, obj):
        return obj.earned_without_admins_commission
    order_value.short_description = 'Вартість замовлення'

    def charged_to_payment_icon(self, obj):
        if obj.charged_to_payment:
            icon_url = static('admin/img/icon-yes.svg')  # Генеруємо URL за допомогою static
            return format_html('<img src="{}" alt="True">', icon_url)  # Використовуємо format_html для безпеки
        else:
            icon_url = static('admin/img/icon-no.svg')  # Генеруємо URL за допомогою static
            return format_html('<img src="{}" alt="False">', icon_url)  # Використовуємо format_html для безпеки

    charged_to_payment_icon.short_description = 'До оплати'

    def paid_in_salary_icon(self, obj):
        if obj.paid_in_salary:
            icon_url = static('admin/img/icon-yes.svg')  # Генеруємо URL за допомогою static
            return format_html('<img src="{}" alt="True">', icon_url)  # Використовуємо format_html для безпеки
        else:
            icon_url = static('admin/img/icon-no.svg')  # Генеруємо URL за допомогою static
            return format_html('<img src="{}" alt="False">', icon_url)  # Використовуємо format_html для безпеки

    paid_in_salary_icon.short_description = 'Оплачено'

