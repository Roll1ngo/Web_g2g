from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
import json

from archive_payments.models import WithdrawalArchive, ReservedFunds
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
        'converted_amount_uah',
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
        'display_payment_details_raw',
        'converted_amount_uah'# Відображення сирого JSON для адмінів
    )
    # Кастомний метод для позначення виплати як виконаної
    actions = ['complete_payment_and_archive']

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

    @admin.action(description='Позначити оплату як виконану та архівувати')
    def complete_payment_and_archive(self, request, queryset):
        """
        Позначає обрані запити на виведення як виконані,
        архівує їх у WithdrawalArchive та переводить оригінальний запит у стан "Не виводити".
        Також оновлює пов'язані записи ReservedFunds.
        """
        archived_count = 0
        reserved_funds_updated_count = 0
        for withdrawal_request in queryset:
            try:
                # 1. Створення запису в архіві
                archive_entry = WithdrawalArchive.objects.create(
                    user=withdrawal_request.user,
                    amount=withdrawal_request.amount,
                    converted_amount_uah = withdrawal_request.converted_amount_uah,
                    withdraw_type=withdrawal_request.withdraw_type,
                    payment_method=withdrawal_request.payment_method,
                    commission_rate=withdrawal_request.commission_rate,
                    withdrawal_date=timezone.now().date(), # Дата архівування - сьогодні
                    created_at=withdrawal_request.created_at, # Зберігаємо оригінальну дату створення
                    payment_details=withdrawal_request.payment_details,
                    # Якщо у вас є логіка для archived_sold_order_ids,
                    # archived_internal_order_ids, archived_commission_breakdown_ids,
                    # додайте її тут. Наприклад:
                    # archived_sold_order_ids=withdrawal_request.related_sold_order_ids,
                    # archived_internal_order_ids=withdrawal_request.related_internal_order_ids,
                    # archived_commission_breakdown_ids=withdrawal_request.related_commission_breakdown_ids,
                )
                archived_count += 1

                # 2. Оновлення пов'язаних записів ReservedFunds
                # Припускаємо, що ReservedFunds пов'язані з WithdrawalRequest
                # за користувачем, сумою та типом 'withdrawal' і статусом 'pending'
                # (або іншим способом, який ви визначили для зв'язку).
                # Якщо у вас є прямий ForeignKey від WithdrawalRequest до ReservedFunds,
                # використовуйте його. Якщо ні, то цей пошук є припущенням.
                related_reserved_funds = ReservedFunds.objects.filter(
                    user=withdrawal_request.user,
                    amount=withdrawal_request.amount, # Припускаємо, що сума збігається
                    reserve_type='withdrawal',
                    status='pending' # Оновлюємо тільки "pending" резерви
                )

                for reserved_fund in related_reserved_funds:
                    reserved_fund.status = 'paid'
                    reserved_fund.archived_id = archive_entry # Прив'язуємо до архівного запису
                    reserved_fund.archived_at = timezone.now() # Встановлюємо дату архівування
                    reserved_fund.save()
                    reserved_funds_updated_count += 1

                # 3. Оновлення поточного запису WithdrawalRequest
                withdrawal_request.withdraw_type = 'do_not_withdraw'
                withdrawal_request.status = 'not_applicable' # Статус, який відповідає 'do_not_withdraw'
                withdrawal_request.amount = None # Очищаємо суму
                withdrawal_request.payment_method = None # Очищаємо метод оплати
                withdrawal_request.commission_rate = None # Очищаємо комісію
                withdrawal_request.scheduled_withdrawal_date = None # Очищаємо заплановану дату
                withdrawal_request.custom_withdrawal_date = None # Очищаємо власну дату
                withdrawal_request.payment_details = None # Очищаємо деталі оплати
                withdrawal_request.converted_amount_uah = None # Очищаємо конвертовану суму
                withdrawal_request.save() # Зберігаємо зміни в оригінальному запиті


            except Exception as e:
                self.message_user(request, f"Помилка обробки запиту {withdrawal_request.id}: {e}", level=messages.ERROR)

        if archived_count > 0:
            self.message_user(request, f"Успішно заархівовано {archived_count} запитів та оновлено їхній статус.", level=messages.SUCCESS)
            if reserved_funds_updated_count > 0:
                self.message_user(request, f"Оновлено {reserved_funds_updated_count} пов'язаних записів резервних коштів.", level=messages.INFO)
        else:
            self.message_user(request, "Немає запитів для архівування або сталася помилка.", level=messages.WARNING)



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
