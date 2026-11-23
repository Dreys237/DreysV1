from django.urls import reverse
from django.utils import timezone

from .models import AuditLog
from .permissions import user_can


def audit(user, company, module, action, obj_repr=""):
    AuditLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        company=company, module=module, action=action, object_repr=str(obj_repr)[:250],
    )


def get_notifications(user, company):
    """Notifications calculées à partir d'événements réellement enregistrés."""
    notes = []
    if company is None:
        return notes
    if user_can(user, "inventory", "view"):
        from apps.inventory.models import Product
        low = [
            p for p in Product.objects.filter(
                company=company, is_stockable=True, is_active=True, min_stock__gt=0
            ).with_stock()
            if p.stock_qty <= p.min_stock
        ]
        if low:
            notes.append({"level": "warn", "text": f"{len(low)} produit(s) sous le seuil minimum",
                          "url": reverse("inventory:product_list") + "?low=1"})
    if user_can(user, "sales", "view"):
        from apps.sales.models import Invoice
        overdue = Invoice.objects.filter(
            company=company, status="validated", due_date__lt=timezone.localdate()
        ).count()
        if overdue:
            notes.append({"level": "danger", "text": f"{overdue} facture(s) échue(s) impayée(s)",
                          "url": reverse("sales:invoice_list") + "?status=overdue"})
    return notes
