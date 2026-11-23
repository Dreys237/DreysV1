from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.partner_list, name="partner_list"),
    path("nouveau/", views.partner_create, name="partner_create"),
    path("<int:pk>/", views.partner_detail, name="partner_detail"),
    path("<int:pk>/modifier/", views.partner_edit, name="partner_edit"),
    path("<int:pk>/convertir/", views.partner_convert, name="partner_convert"),
    path("<int:pk>/echange/", views.interaction_add, name="interaction_add"),
    path("<int:pk>/supprimer/", views.partner_delete, name="partner_delete"),
]
