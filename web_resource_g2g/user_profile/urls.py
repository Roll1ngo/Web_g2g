from django.urls import path
from . import views

app_name = 'user_profile'

urlpatterns = [
    path('', views.profile_main_page, name='profile_main_page'),
    path('rules/', views.rules, name='rules'),
    path('withdraw/', views.withdraw_page, name='withdraw_page'),
    path('deposit_page/', views.deposit_page, name='deposit_page'),
    path('create_order_instruction/', views.create_order_instruction, name='create_order_instruction'),
    path('security_and_privacy_policy/', views.security_and_privacy_policy, name='security_and_privacy_policy'),
]