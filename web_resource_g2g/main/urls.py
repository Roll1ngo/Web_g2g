from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('update_table_data/', views.update_table_data, name='update_table_data'),
    path('add_server/', views.add_server, name='add_server'),
    path('handle_option_change/', views.handle_option_change, name='handle_option_change'),
    path('show_order_info/<int:server_id>/', views.show_order_info, name='show_order_info'),
    path('upload_video/<int:sold_order_number>/', views.upload_video, name='upload_video'),
    path('history_orders/', views.show_history_orders, name='history_orders'),
]
