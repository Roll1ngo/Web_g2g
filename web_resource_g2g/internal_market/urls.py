from django.urls import path
from . import views

app_name = 'internal_market'

urlpatterns = [
    path('market/', views.main_page, name='main_page'),
    path('create_order_from_form/', views.create_order_from_form, name='create_order_from_form'),

]