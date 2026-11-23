from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Company
from apps.crm.models import Partner
from apps.inventory.models import Product

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def q2(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class Invoice(models.Model):
    STATUSES = [("draft", "Brouillon"), ("validated", "Validée"), ("paid", "Payée"), ("cancelled", "Annulée")]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    number = models.CharField("Numéro", max_length=30, null=True, blank=True)
    customer = models.ForeignKey(Partner, on_delete=models.PROTECT, verbose_name="Client")
    date = models.DateField("Date", default=timezone.localdate)
    due_date = models.DateField("Échéance", null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="draft")
    notes = models.TextField("Notes", blank=True)
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(default=timezone.now)
    validated_at = models.DateTimeField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.UniqueConstraint(fields=["company", "number"], name="uniq_invoice_number")]

    def __str__(self):
        return self.number or f"Brouillon #{self.pk}"

    def recompute(self):
        ht = tax = Decimal("0")
        for line in self.lines.all():
            l_ht, l_tax = line.amounts()
            ht += l_ht
            tax += l_tax
        self.total_ht, self.total_tax, self.total_ttc = q2(ht), q2(tax), q2(ht + tax)
        self.save(update_fields=["total_ht", "total_tax", "total_ttc"])

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))

    @property
    def balance(self):
        return self.total_ttc - self.amount_paid

    @property
    def is_overdue(self):
        return self.status == "validated" and self.due_date is not None and self.due_date < timezone.localdate()


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Produit")
    description = models.CharField("Description", max_length=250, blank=True)
    quantity = models.DecimalField("Qté", max_digits=14, decimal_places=3, default=1)
    unit_price = models.DecimalField("Prix unitaire", max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField("Remise (%)", max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField("Taxe (%)", max_digits=5, decimal_places=2, default=0)

    def amounts(self):
        ht = q2(self.quantity * self.unit_price * (HUNDRED - self.discount) / HUNDRED)
        tax = q2(ht * self.tax_rate / HUNDRED)
        return ht, tax

    @property
    def line_ht(self):
        return self.amounts()[0]

    @property
    def line_ttc(self):
        ht, tax = self.amounts()
        return ht + tax


class Payment(models.Model):
    METHODS = [("cash", "Espèces"), ("bank", "Virement / banque"), ("mtn", "MTN Mobile Money"),
               ("orange", "Orange Money"), ("other", "Autre")]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    date = models.DateField("Date", default=timezone.localdate)
    amount = models.DecimalField("Montant", max_digits=14, decimal_places=2)
    method = models.CharField("Mode", max_length=10, choices=METHODS, default="cash")
    reference = models.CharField("Référence", max_length=100, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["date", "id"]
