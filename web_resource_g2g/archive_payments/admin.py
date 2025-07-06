from django.contrib import admin
from .models import WithdrawalArchive, ReservedFunds

# Реєстрація моделі WithdrawalArchive в адмін-панелі
@admin.register(WithdrawalArchive)
class WithdrawalArchiveAdmin(admin.ModelAdmin):
    # Поля, які будуть відображатися у списку об'єктів
    list_display = (
        'user',
        'amount',
        'converted_amount_uah',
        'withdraw_type',
        'payment_method',
        'commission_rate',
        'withdrawal_date',
        'created_at',
        'archived_sold_order_ids',
        'archived_internal_order_ids',
        'archived_commission_breakdown_ids',
    )
    # Поля, за якими можна здійснювати пошук
    search_fields = (
        'user__username', # Дозволяє шукати за іменем користувача
        'withdraw_type',
        'payment_method',
    )
    # Поля, за якими можна фільтрувати список
    list_filter = (
        'user',
        'withdraw_type',
        'payment_method',
        'withdrawal_date',
        'created_at',
    )
    # Поля, які будуть відображатися як посилання на сторінку редагування
    list_display_links = (
        'user',
        'amount',
    )
    # Поля, які відображаються у детальному перегляді, згруповані за секціями
    fieldsets = (
        (None, {
            'fields': ('user', 'amount', 'withdraw_type', 'payment_method', 'commission_rate', 'payment_details')
        }),
        ('Дати', {
            'fields': ('withdrawal_date', 'created_at'),
            'classes': ('collapse',), # Зробить секцію згортаємою
        }),
        ('Архівні ID', {
            'fields': ('archived_sold_order_ids', 'archived_internal_order_ids', 'archived_commission_breakdown_ids'),
            'classes': ('collapse',),
        }),
    )
    # Зробити created_at тільки для читання
    readonly_fields = ('created_at',)


# Реєстрація моделі ReservedFunds в адмін-панелі
@admin.register(ReservedFunds)
class ReservedFundsAdmin(admin.ModelAdmin):
    # Поля, які будуть відображатися у списку об'єктів
    list_display = (
        'user',
        'amount',
        'reserve_type',
        'status',
        'created_at',
        'archived_id',
        'archived_at',
        'archived_id__archived_sold_order_ids',
        'archived_id__archived_internal_order_ids',
        'archived_id__archived_commission_breakdown_ids',

    )
    # Поля, за якими можна здійснювати пошук
    search_fields = (
        'user__username',
        'reserve_type',
        'status',
    )
    # Поля, за якими можна фільтрувати список
    list_filter = (
        'reserve_type',
        'status',
        'created_at',
        'archived_at',
    )
    # Поля, які будуть відображатися як посилання на сторінку редагування
    list_display_links = (
        'user',
        'amount',
    )
    # Поля, які можна редагувати безпосередньо зі списку
    list_editable = (
        'status',
    )
    # Поля, які відображаються у детальному перегляді, згруповані за секціями
    fieldsets = (
        (None, {
            'fields': ('user', 'amount', 'reserve_type', 'status')
        }),
        ('Архівна інформація', {
            'fields': ('archived_id', 'archived_at'),
            'classes': ('collapse',),
        }),
    )
    # Зробити created_at та archived_at тільки для читання
    readonly_fields = ('created_at', 'archived_at',)

