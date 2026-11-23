from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import StyledForm, StyledModelForm
from apps.crm.models import Partner
from apps.inventory.models import Product

from .models import Invoice, InvoiceLine, Payment


class InvoiceForm(StyledModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "date", "due_date", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Partner.objects.filter(company=company, kind="customer")
        self.fields["customer"].help_text = "Seuls les clients sont proposés. Convertissez un prospect depuis le CRM."

    def clean(self):
        data = super().clean()
        if data.get("date") and data.get("due_date") and data["due_date"] < data["date"]:
            self.add_error("due_date", "L'échéance ne peut pas précéder la date de la facture.")
        return data


class InvoiceLineForm(StyledModelForm):
    description = forms.CharField(label="Description", required=False, max_length=250)
    unit_price = forms.DecimalField(label="Prix unitaire", required=False, min_value=0,
                                    max_digits=14, decimal_places=2)
    discount = forms.DecimalField(label="Remise (%)", required=False, min_value=0, max_value=100,
                                  max_digits=5, decimal_places=2)
    tax_rate = forms.DecimalField(label="Taxe (%)", required=False, min_value=0, max_value=100,
                                  max_digits=5, decimal_places=2)

    class Meta:
        model = InvoiceLine
        fields = ["product", "description", "quantity", "unit_price", "discount", "tax_rate"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["product"].queryset = Product.objects.filter(company=company, is_active=True)
        self.fields["quantity"].required = False
        if not self.instance.pk:  # nouvelle ligne : champs vides => valeurs reprises du produit / de la société
            for name in ("quantity", "unit_price", "discount", "tax_rate"):
                self.initial.pop(name, None)
                self.fields[name].initial = None
        for name in ("unit_price", "discount", "tax_rate"):
            self.fields[name].widget.attrs["class"] = "input num"
        self.fields["quantity"].widget.attrs["class"] = "input num"

    def clean(self):
        data = super().clean()
        product = data.get("product")
        if not self.has_changed():
            return data
        if not product and not data.get("description"):
            raise forms.ValidationError("Choisissez un produit ou saisissez une description.")
        qty = data.get("quantity")
        if qty is None:
            qty = Decimal("1")
        if qty <= 0:
            self.add_error("quantity", "La quantité doit être positive.")
        data["quantity"] = qty
        if not data.get("description") and product:
            data["description"] = product.name
        if data.get("unit_price") is None:
            data["unit_price"] = product.sale_price if product else Decimal("0")
        if data.get("discount") is None:
            data["discount"] = Decimal("0")
        if data.get("tax_rate") is None:
            data["tax_rate"] = self.company.default_tax_rate
        return data


def line_formset(extra):
    return inlineformset_factory(Invoice, InvoiceLine, form=InvoiceLineForm, extra=extra, can_delete=True)


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = ["date", "amount", "method", "reference"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
