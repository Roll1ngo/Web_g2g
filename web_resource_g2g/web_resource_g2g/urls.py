from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("", include("users.urls")),
    path("internal_market/", include("internal_market.urls")),
] +  static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

