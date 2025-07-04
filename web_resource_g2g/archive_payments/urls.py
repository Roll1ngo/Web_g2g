from django.urls import path
from . import views

app_name = 'archive_payments'

urlpatterns = [
    path('', views.archive_payments_page, name='archive_payments'),
]