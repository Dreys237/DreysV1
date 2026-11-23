from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Sequence
from apps.core.services import audit
from apps.inventory.services import record_movement

from .models import Invoice, Payment, q2


@transaction.atomic
def validate_invoice(invoice_id, user=None):
    """Valide une facture : numérotation, sorties de stock, le tout dans une transaction."""
    invoice = Invoice.objects.select_for_update().select_related("company").get(pk=invoice_id)
    if invoice.status != "draft":
        raise ValidationError("Seule une facture en brouillon peut être validée.")
    lines = list(invoice.lines.select_related("product"))
    if not lines:
        raise ValidationError("Ajoutez au moins une ligne avant de valider.")
    invoice.recompute()
    invoice.number = Sequence.next(invoice.company, "FAC")
    for line in lines:
        if line.product_id and line.product.is_stockable:
            record_movement(invoice.company, line.product, -line.quantity, "out", user=user,
                            reference=invoice.number, note="Vente")
    invoice.status = "validated"
    invoice.validated_at = timezone.now()
    invoice.save(update_fields=["number", "status", "validated_at"])
    audit(user, invoice.company, "sales", "Facture validée", invoice.number)
    return invoice


@transaction.atomic
def cancel_invoice(invoice_id, user=None):
    """Annule une facture validée non payée et remet le stock (mouvements inverses)."""
    invoice = Invoice.objects.select_for_update().select_related("company").get(pk=invoice_id)
    if invoice.status != "validated":
        raise ValidationError("Seule une facture validée peut être annulée.")
    if invoice.payments.exists():
        raise ValidationError("Cette facture a des paiements : elle ne peut pas être annulée.")
    for line in invoice.lines.select_related("product"):
        if line.product_id and line.product.is_stockable:
            record_movement(invoice.company, line.product, line.quantity, "in", user=user,
                            reference=invoice.number, note="Annulation facture")
    invoice.status = "cancelled"
    invoice.save(update_fields=["status"])
    audit(user, invoice.company, "sales", "Facture annulée", invoice.number)
    return invoice


@transaction.atomic
def record_payment(invoice_id, amount, method, date, reference="", user=None):
    invoice = Invoice.objects.select_for_update().select_related("company").get(pk=invoice_id)
    amount = q2(Decimal(amount))
    if invoice.status != "validated":
        raise ValidationError("Les paiements ne s'enregistrent que sur une facture validée non soldée.")
    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")
    if amount > invoice.balance:
        raise ValidationError("Le montant dépasse le solde restant dû.")
    payment = Payment.objects.create(invoice=invoice, amount=amount, method=method, date=date,
                                     reference=reference, user=user)
    if invoice.balance <= 0:
        invoice.status = "paid"
        invoice.save(update_fields=["status"])
    audit(user, invoice.company, "sales", "Paiement enregistré", f"{invoice.number} — {amount}")
    return payment
