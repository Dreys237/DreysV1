from decimal import Decimal

from django import forms

from apps.core.forms import StyledForm, StyledModelForm

from .models import Category, Product, StockMovement


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["sku", "name", "category", "unit", "barcode", "sale_price", "cost_price",
                  "min_stock", "is_stockable", "is_active"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["category"].queryset = Category.objects.filter(company=company)

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        qs = Product.objects.filter(company=self.company, sku__iexact=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette référence existe déjà.")
        return sku

    def clean(self):
        data = super().clean()
        for f in ("sale_price", "cost_price", "min_stock"):
            if data.get(f) is not None and data[f] < 0:
                self.add_error(f, "La valeur ne peut pas être négative.")
        return data


class MovementForm(StyledForm):
    product = forms.ModelChoiceField(label="Produit", queryset=Product.objects.none())
    kind = forms.ChoiceField(label="Type d'opération", choices=StockMovement.KINDS)
    quantity = forms.DecimalField(
        label="Quantité", max_digits=14, decimal_places=3,
        help_text="Positive pour une entrée ou une sortie. Pour un ajustement : positive (+) ou négative (−).")
    reference = forms.CharField(label="Référence", required=False, max_length=100)
    note = forms.CharField(label="Note", required=False, max_length=250)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            company=company, is_stockable=True, is_active=True)

    def clean(self):
        data = super().clean()
        qty, kind = data.get("quantity"), data.get("kind")
        if qty is not None and kind in ("in", "out") and qty <= 0:
            self.add_error("quantity", "Saisissez une quantité positive.")
        if qty is not None and kind == "adjust" and qty == 0:
            self.add_error("quantity", "La quantité ne peut pas être nulle.")
        return data

    def signed_quantity(self):
        qty, kind = self.cleaned_data["quantity"], self.cleaned_data["kind"]
        return -qty if kind == "out" else Decimal(qty)
