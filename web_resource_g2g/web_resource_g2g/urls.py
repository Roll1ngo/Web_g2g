
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("", include("users.urls")),
    path("internal_market/", include("internal_market.urls")),
    path('accounts/', include('allauth.urls')),
    path('profile/', include('user_profile.urls')),
    path('archive_payments/', include('archive_payments.urls'))
    ]
