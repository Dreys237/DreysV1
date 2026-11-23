from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("gestion-technique/", admin.site.urls),
    path("crm/", include("apps.crm.urls")),
    path("ventes/", include("apps.sales.urls")),
    path("stock/", include("apps.inventory.urls")),
    path("", include("apps.core.urls")),
]
