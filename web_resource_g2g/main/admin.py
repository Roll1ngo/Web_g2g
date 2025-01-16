from django.contrib import admin
from .models import Sellers


@admin.register(Sellers)
class SellersAdmin(admin.ModelAdmin):
    list_display = ('id_telegram', 'balance', 'interest_rate', 'auth_user')  # замініть на поля вашої моделі
    list_editable = ('balance', 'interest_rate')  # поля, які можна редагувати прямо у списку
    search_fields = ('id_telegram', 'balance', 'interest_rate', 'auth_user')  # поля для пошуку
