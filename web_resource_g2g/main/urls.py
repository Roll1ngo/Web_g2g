from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('update_table_data/', views.update_table_data, name='update_table_data'),
    path('add_server/', views.add_server, name='add_server'),
    path('about/', views.about, name='about'),
    ]