from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Company(models.Model):
    name = models.CharField("Nom commercial", max_length=150)
    legal_name = models.CharField("Raison sociale", max_length=200, blank=True)
    tax_id = models.CharField("N° contribuable (NIU)", max_length=50, blank=True)
    address = models.CharField("Adresse", max_length=250, blank=True)
    city = models.CharField("Ville", max_length=100, blank=True)
    country = models.CharField("Pays", max_length=100, default="Cameroun")
    phone = models.CharField("Téléphone", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    currency = models.CharField("Devise", max_length=3, default="XAF")
    default_tax_rate = models.DecimalField(
        "Taux de taxe par défaut (%)", max_digits=5, decimal_places=2, default=0,
        help_text="0 par défaut. Ce taux doit être validé par un professionnel compétent au Cameroun.",
    )
    allow_negative_stock = models.BooleanField("Autoriser le stock négatif", default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Société"
        verbose_name_plural = "Sociétés"

    def __str__(self):
        return self.name


class Module(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default="▣")
    description = models.CharField(max_length=250, blank=True)
    sequence = models.PositiveSmallIntegerField(default=100)
    is_implemented = models.BooleanField("Développé", default=False)
    is_active = models.BooleanField("Activé", default=False)
    depends_on = models.ManyToManyField("self", symmetrical=False, related_name="required_by", blank=True)

    class Meta:
        ordering = ["sequence", "name"]

    def __str__(self):
        return self.name


class Role(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    can_view = models.BooleanField("Consulter", default=False)
    can_create = models.BooleanField("Créer", default=False)
    can_edit = models.BooleanField("Modifier", default=False)
    can_validate = models.BooleanField("Valider", default=False)
    can_cancel = models.BooleanField("Annuler", default=False)
    can_delete = models.BooleanField("Supprimer", default=False)
    can_export = models.BooleanField("Exporter", default=False)

    class Meta:
        unique_together = [("role", "module")]


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Profil de {self.user}"


class AuditLog(models.Model):
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    module = models.CharField(max_length=50, blank=True)
    action = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=250, blank=True)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created", "-id"]


class Sequence(models.Model):
    """Numérotation automatique (ex. FAC-2026-00001), protégée contre les doublons."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    code = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("company", "code", "year")]

    @classmethod
    def next(cls, company, code):
        year = timezone.localdate().year
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(company=company, code=code, year=year)
            seq.last += 1
            seq.save(update_fields=["last"])
            return f"{code}-{year}-{seq.last:05d}"
