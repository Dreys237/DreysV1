from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import get_company, module_required
from apps.core.services import audit
from apps.core.utils import paginate

from .forms import MovementForm, ProductForm
from .models import Product, StockMovement
from .services import record_movement


@module_required("inventory", "view")
def product_list(request):
    qs = Product.objects.filter(company=get_company(request)).with_stock().select_related("category").order_by("name")
    q = request.GET.get("q", "").strip()
    low = request.GET.get("low") == "1"
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    if low:
        qs = [p for p in qs if p.is_stockable and p.min_stock > 0 and p.stock_qty <= p.min_stock]
    return render(request, "inventory/product_list.html", {"page": paginate(request, qs), "q": q, "low": low})


@module_required("inventory", "create")
def product_create(request):
    company = get_company(request)
    form = ProductForm(request.POST or None, company=company)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.company = company
        product.save()
        audit(request.user, company, "inventory", "Produit créé", product.name)
        messages.success(request, f"Produit « {product.name} » créé.")
        return redirect("inventory:product_detail", pk=product.pk)
    return render(request, "form.html", {"form": form, "title": "Nouveau produit",
                                         "cancel_url": "inventory:product_list"})


@module_required("inventory", "view")
def product_detail(request, pk):
    company = get_company(request)
    product = get_object_or_404(Product.objects.with_stock(), pk=pk, company=company)
    return render(request, "inventory/product_detail.html", {
        "product": product, "movements": product.movements.select_related("warehouse", "user")[:30]})


@module_required("inventory", "edit")
def product_edit(request, pk):
    company = get_company(request)
    product = get_object_or_404(Product, pk=pk, company=company)
    form = ProductForm(request.POST or None, instance=product, company=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, company, "inventory", "Produit modifié", product.name)
        messages.success(request, "Modifications enregistrées.")
        return redirect("inventory:product_detail", pk=product.pk)
    return render(request, "form.html", {"form": form, "title": f"Modifier {product.name}",
                                         "cancel_url": "inventory:product_list"})


@module_required("inventory", "delete")
@require_POST
def product_delete(request, pk):
    company = get_company(request)
    product = get_object_or_404(Product, pk=pk, company=company)
    try:
        name = product.name
        product.delete()
    except ProtectedError:
        messages.error(request, "Suppression impossible : ce produit a des mouvements. Désactivez-le plutôt.")
        return redirect("inventory:product_detail", pk=pk)
    audit(request.user, company, "inventory", "Produit supprimé", name)
    messages.success(request, f"« {name} » supprimé.")
    return redirect("inventory:product_list")


@module_required("inventory", "create")
def movement_create(request):
    company = get_company(request)
    initial = {}
    if request.GET.get("product"):
        initial["product"] = request.GET["product"]
    form = MovementForm(request.POST or None, company=company, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            record_movement(company, d["product"], form.signed_quantity(), d["kind"], user=request.user,
                            reference=d["reference"], note=d["note"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request.user, company, "inventory", f"Mouvement ({d['kind']})", d["product"].name)
            messages.success(request, "Mouvement de stock enregistré.")
            return redirect("inventory:product_detail", pk=d["product"].pk)
    return render(request, "form.html", {"form": form, "title": "Mouvement de stock",
                                         "cancel_url": "inventory:product_list"})


@module_required("inventory", "view")
def movement_list(request):
    qs = StockMovement.objects.filter(company=get_company(request)).select_related(
        "product", "warehouse", "user")
    return render(request, "inventory/movement_list.html", {"page": paginate(request, qs, 40)})
