from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('update_table_data/', views.update_table_data, name='update_table_data'),
    ]