from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import Product, StockMovement, Warehouse


def get_default_warehouse(company):
    wh = Warehouse.objects.filter(company=company, is_default=True).first()
    if wh is None:
        wh, _ = Warehouse.objects.get_or_create(
            company=company, name="Entrepôt principal", defaults={"is_default": True})
        if not wh.is_default:
            wh.is_default = True
            wh.save(update_fields=["is_default"])
    return wh


def current_stock(product):
    return product.movements.aggregate(s=Sum("quantity"))["s"] or Decimal("0")


@transaction.atomic
def record_movement(company, product, quantity, kind, user=None, reference="", note="", warehouse=None):
    """Enregistre un mouvement (quantité signée) de façon transactionnelle.

    Refuse un stock négatif sauf si la société l'autorise.
    """
    quantity = Decimal(quantity)
    if quantity == 0:
        raise ValidationError("La quantité ne peut pas être nulle.")
    product = Product.objects.select_for_update().get(pk=product.pk, company=company)
    if not product.is_stockable:
        raise ValidationError(f"« {product.name} » n'est pas un produit stockable.")
    if quantity < 0 and not company.allow_negative_stock:
        available = current_stock(product)
        if available + quantity < 0:
            raise ValidationError(
                f"Stock insuffisant pour « {product.name} » (disponible : {available.normalize():f}).")
    return StockMovement.objects.create(
        company=company, product=product, warehouse=warehouse or get_default_warehouse(company),
        quantity=quantity, kind=kind, reference=reference, note=note, user=user)
