from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("produits/nouveau/", views.product_create, name="product_create"),
    path("produits/<int:pk>/", views.product_detail, name="product_detail"),
    path("produits/<int:pk>/modifier/", views.product_edit, name="product_edit"),
    path("produits/<int:pk>/supprimer/", views.product_delete, name="product_delete"),
    path("mouvements/", views.movement_list, name="movement_list"),
    path("mouvements/nouveau/", views.movement_create, name="movement_create"),
]
