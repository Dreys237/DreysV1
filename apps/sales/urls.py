from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.invoice_list, name="invoice_list"),
    path("factures/nouvelle/", views.invoice_create, name="invoice_create"),
    path("factures/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("factures/<int:pk>/modifier/", views.invoice_edit, name="invoice_edit"),
    path("factures/<int:pk>/valider/", views.invoice_validate, name="invoice_validate"),
    path("factures/<int:pk>/annuler/", views.invoice_cancel, name="invoice_cancel"),
    path("factures/<int:pk>/paiement/", views.payment_add, name="payment_add"),
    path("factures/<int:pk>/supprimer/", views.invoice_delete, name="invoice_delete"),
]
