from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Company


class Partner(models.Model):
    KINDS = [("prospect", "Prospect"), ("customer", "Client"), ("supplier", "Fournisseur")]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    kind = models.CharField("Type", max_length=10, choices=KINDS, default="prospect")
    name = models.CharField("Nom", max_length=200)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Téléphone", max_length=50, blank=True)
    address = models.CharField("Adresse", max_length=250, blank=True)
    city = models.CharField("Ville", max_length=100, blank=True)
    tax_id = models.CharField("N° contribuable (NIU)", max_length=50, blank=True)
    notes = models.TextField("Notes", blank=True)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+", verbose_name="Commercial")
    is_demo = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Interaction(models.Model):
    KINDS = [("note", "Note"), ("call", "Appel"), ("meeting", "Rendez-vous"), ("email", "Email")]

    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="interactions")
    kind = models.CharField("Type", max_length=10, choices=KINDS, default="note")
    text = models.TextField("Détail")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created"]
