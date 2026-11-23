from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.models import Company


class Warehouse(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField("Nom", max_length=100)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = [("company", "name")]

    def __str__(self):
        return self.name


class Category(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField("Nom", max_length=100)

    class Meta:
        unique_together = [("company", "name")]
        ordering = ["name"]
        verbose_name_plural = "catégories"

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def with_stock(self):
        return self.annotate(stock_qty=Coalesce(
            Sum("movements__quantity"), Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=3)))


class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    sku = models.CharField("Référence (SKU)", max_length=50)
    name = models.CharField("Désignation", max_length=200)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL,
                                 verbose_name="Catégorie")
    unit = models.CharField("Unité", max_length=20, default="pièce")
    barcode = models.CharField("Code-barres", max_length=64, blank=True)
    sale_price = models.DecimalField("Prix de vente", max_digits=14, decimal_places=2, default=0)
    cost_price = models.DecimalField("Coût de revient", max_digits=14, decimal_places=2, default=0)
    min_stock = models.DecimalField("Seuil minimum", max_digits=14, decimal_places=3, default=0)
    is_stockable = models.BooleanField("Produit stockable", default=True)
    is_active = models.BooleanField("Actif", default=True)
    is_demo = models.BooleanField(default=False)
    created = models.DateTimeField(default=timezone.now)

    objects = ProductQuerySet.as_manager()

    class Meta:
        unique_together = [("company", "sku")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class StockMovement(models.Model):
    KINDS = [("in", "Entrée"), ("out", "Sortie"), ("adjust", "Ajustement")]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    quantity = models.DecimalField("Quantité (signée)", max_digits=14, decimal_places=3)
    kind = models.CharField(max_length=10, choices=KINDS)
    reference = models.CharField("Référence", max_length=100, blank=True)
    note = models.CharField("Note", max_length=250, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created", "-id"]
