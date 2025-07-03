from django.contrib import admin
from django.utils.html import format_html
import json
from .models import WithdrawalRequest # Імпортуйте вашу модель WithdrawalRequest

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    """
    Клас для налаштування відображення моделі WithdrawalRequest в адмін-панелі Django.
    """

    # Поля, які відображатимуться у списку запитів на виведення
    list_display = (
        'id',
        'user_link',  # Використовуємо кастомний метод для посилання на користувача
        'amount',
        'withdraw_type',
        'payment_method',
        'status',
        'scheduled_withdrawal_date',
        'created_at',
        'display_payment_details_summary', # Кастомний метод для короткого відображення деталей оплати
    )

    # Поля, за якими можна фільтрувати список
    list_filter = (
        'withdraw_type',
        'payment_method',
        'status',
        'scheduled_withdrawal_date',
        'created_at',
    )

    # Поля, за якими можна здійснювати пошук
    search_fields = (
        'user__username',  # Пошук за ім'ям користувача
        'user__email',     # Пошук за email користувача
        'payment_details', # Пошук у JSON-полі (залежить від підтримки БД)
        'id',              # Пошук за ID запиту
    )

    # Поля, які не можна редагувати після створення об'єкта
    readonly_fields = (
        'created_at',
        'updated_at',
        'display_payment_details_raw', # Відображення сирого JSON для адмінів
    )

    # Використовувати поле введення ID замість випадаючого списку для ForeignKey
    # Це корисно, коли пов'язаних об'єктів (користувачів) дуже багато.
    raw_id_fields = ('user',)

    # Організація полів у формі редагування/створення об'єкта
    fieldsets = (
        (None, {
            'fields': ('user', 'withdraw_type', 'payment_method', 'amount', 'payment_details')
        }),
        ('Дати та Комісія', {
            'fields': ('commission_rate', 'scheduled_withdrawal_date', 'custom_withdrawal_date', 'status')
        }),
        ('Системна інформація', {
            'fields': ('created_at', 'updated_at', 'display_payment_details_raw'),
            'classes': ('collapse',), # Зробити цю секцію згортаємою
            'description': 'Ці поля генеруються автоматично і не можуть бути змінені вручну.'
        }),
    )

    # Кастомний метод для створення посилання на користувача в list_display
    def user_link(self, obj):
        return format_html('<a href="{}">{}</a>',
                           f'/admin/auth/user/{obj.user.pk}/change/', # Шлях до сторінки редагування користувача
                           obj.user.username)
    user_link.short_description = "Користувач" # Назва колонки
    user_link.admin_order_field = 'user__username' # Дозволяє сортувати за ім'ям користувача

    # Кастомний метод для короткого відображення деталей оплати в list_display
    def display_payment_details_summary(self, obj):
        if obj.payment_details and 'account_info' in obj.payment_details:
            return obj.payment_details['account_info']
        return "Не вказано"
    display_payment_details_summary.short_description = "Деталі оплати"

    # Кастомний метод для відображення сирого JSON у readonly_fields
    def display_payment_details_raw(self, obj):
        if obj.payment_details:
            # Використовуємо json.dumps для форматованого виводу JSON
            return format_html('<pre>{}</pre>', json.dumps(obj.payment_details, indent=2, ensure_ascii=False))
        return "Немає"
    display_payment_details_raw.short_description = "Деталі оплати (JSON)"
