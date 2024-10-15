from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.start_page, name='start_page'),
]