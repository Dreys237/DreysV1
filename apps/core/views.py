import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CompanyForm, UserForm
from .models import AuditLog, Module, Role, RolePermission
from .permissions import ACTIONS, admin_required, get_company, get_profile, user_can
from .services import audit
from .utils import paginate

User = get_user_model()


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    for f in form.fields.values():
        f.widget.attrs["class"] = "input"
    if request.method == "POST":
        ip = request.META.get("REMOTE_ADDR", "")
        key = f"login-fail:{ip}:{request.POST.get('username', '').lower()}"
        if cache.get(key, 0) >= settings.LOGIN_MAX_ATTEMPTS:
            form.errors["__all__"] = form.error_class(
                ["Trop de tentatives. Réessayez dans quelques minutes."])
        elif form.is_valid():
            cache.delete(key)
            login(request, form.get_user())
            nxt = request.POST.get("next") or request.GET.get("next") or ""
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect("core:dashboard")
        else:
            cache.set(key, cache.get(key, 0) + 1, settings.LOGIN_LOCK_SECONDS)
    return render(request, "core/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:login")


@login_required
def dashboard(request):
    company = get_company(request)
    ctx = {"company": company}
    user = request.user
    if user_can(user, "crm", "view"):
        from apps.crm.models import Partner
        partners = Partner.objects.filter(company=company)
        ctx["n_customers"] = partners.filter(kind="customer").count()
        ctx["n_prospects"] = partners.filter(kind="prospect").count()
        ctx["n_suppliers"] = partners.filter(kind="supplier").count()
    if user_can(user, "inventory", "view"):
        from apps.inventory.models import Product
        products = list(Product.objects.filter(company=company, is_active=True).with_stock())
        ctx["n_products"] = len(products)
        ctx["stock_value"] = sum(
            (p.stock_qty * p.cost_price for p in products if p.is_stockable), Decimal("0"))
        ctx["low_stock"] = [p for p in products if p.is_stockable and p.min_stock > 0
                            and p.stock_qty <= p.min_stock][:8]
    if user_can(user, "sales", "view"):
        from apps.sales.models import Invoice
        today = date.today()
        valid = list(Invoice.objects.filter(company=company, status__in=["validated", "paid"]))
        ctx["revenue_ht"] = sum((i.total_ht for i in valid), Decimal("0"))
        open_inv = [i for i in valid if i.status == "validated"]
        ctx["receivables"] = sum((i.balance for i in open_inv), Decimal("0"))
        ctx["n_unpaid"] = len(open_inv)
        ctx["n_overdue"] = sum(1 for i in open_inv if i.due_date and i.due_date < today)
        ctx["n_drafts"] = Invoice.objects.filter(company=company, status="draft").count()
        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        totals = {k: Decimal("0") for k in months}
        for inv in valid:
            k = (inv.date.year, inv.date.month)
            if k in totals:
                totals[k] += inv.total_ht
        peak = max(totals.values()) or Decimal("1")
        ctx["chart"] = [{"label": f"{mm:02d}/{yy}", "value": v,
                         "pct": int((v / peak) * 100)} for (yy, mm), v in totals.items()]
    if is_any_admin(user):
        ctx["recent"] = AuditLog.objects.filter(company=company)[:8]
    return render(request, "core/dashboard.html", ctx)


def is_any_admin(user):
    from .permissions import is_admin
    return is_admin(user)


@login_required
def catalog(request):
    return render(request, "core/catalog.html", {"modules": Module.objects.prefetch_related("depends_on")})


@admin_required
@require_POST
def module_toggle(request, code):
    module = get_object_or_404(Module, code=code)
    company = get_company(request)
    if not module.is_implemented:
        messages.error(request, f"« {module.name} » n'est pas encore développé.")
    elif module.is_active:
        dependants = module.required_by.filter(is_active=True)
        if dependants.exists():
            names = ", ".join(d.name for d in dependants)
            messages.error(request, f"Impossible de désactiver « {module.name} » : requis par {names}.")
        else:
            module.is_active = False
            module.save(update_fields=["is_active"])
            audit(request.user, company, "core", "Module désactivé", module.name)
            messages.success(request, f"« {module.name} » désactivé.")
    else:
        missing = module.depends_on.filter(is_active=False)
        if missing.exists():
            names = ", ".join(d.name for d in missing)
            messages.error(request, f"Activez d'abord : {names}.")
        else:
            module.is_active = True
            module.save(update_fields=["is_active"])
            audit(request.user, company, "core", "Module activé", module.name)
            messages.success(request, f"« {module.name} » activé.")
    return redirect("core:catalog")


@admin_required
def users(request):
    company = get_company(request)
    qs = User.objects.select_related("profile__role").filter(
        Q(profile__company=company) | Q(profile__isnull=True)).order_by("username")
    return render(request, "core/users.html", {"users": qs})


@admin_required
def user_create(request):
    company = get_company(request)
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(company)
        audit(request.user, company, "core", "Utilisateur créé", user.username)
        messages.success(request, f"Utilisateur « {user.username} » créé.")
        return redirect("core:users")
    return render(request, "form.html", {"form": form, "title": "Nouvel utilisateur",
                                         "cancel_url": "core:users"})


@admin_required
def user_edit(request, pk):
    company = get_company(request)
    target = get_object_or_404(User, pk=pk)
    get_profile(target)
    form = UserForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        if target == request.user and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Vous ne pouvez pas désactiver votre propre compte.")
        else:
            form.save(company)
            audit(request.user, company, "core", "Utilisateur modifié", target.username)
            messages.success(request, "Utilisateur mis à jour.")
            return redirect("core:users")
    return render(request, "form.html", {"form": form, "title": f"Modifier {target.username}",
                                         "cancel_url": "core:users"})


@admin_required
def roles(request):
    return render(request, "core/roles.html", {"roles": Role.objects.all()})


@admin_required
def role_edit(request, pk):
    role = get_object_or_404(Role, pk=pk)
    mods = list(Module.objects.filter(is_implemented=True))
    if request.method == "POST":
        if role.code in ("super_admin", "admin"):
            messages.error(request, "Les rôles administrateurs ont tous les droits sur les modules actifs.")
            return redirect("core:roles")
        for m in mods:
            flags = {f"can_{a}": request.POST.get(f"{m.code}__{a}") == "on" for a in ACTIONS}
            RolePermission.objects.update_or_create(role=role, module=m, defaults=flags)
        audit(request.user, get_company(request), "core", "Permissions modifiées", role.name)
        messages.success(request, f"Permissions du rôle « {role.name} » enregistrées.")
        return redirect("core:roles")
    perms = {p.module_id: p for p in role.permissions.all()}
    rows = []
    for m in mods:
        p = perms.get(m.pk)
        rows.append({"module": m, "cells": [
            {"name": f"{m.code}__{a}", "checked": bool(p and getattr(p, f"can_{a}"))} for a in ACTIONS]})
    labels = ["Consulter", "Créer", "Modifier", "Valider", "Annuler", "Supprimer", "Exporter"]
    return render(request, "core/role_edit.html", {"role": role, "rows": rows, "labels": labels})


@admin_required
def company_settings(request):
    company = get_company(request)
    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, company, "core", "Paramètres société modifiés", company.name)
        messages.success(request, "Paramètres enregistrés.")
        return redirect("core:company")
    return render(request, "form.html", {"form": form, "title": "Paramètres de la société",
                                         "cancel_url": "core:dashboard"})


@admin_required
def audit_log(request):
    page = paginate(request, AuditLog.objects.filter(company=get_company(request)).select_related("user"), 40)
    return render(request, "core/audit.html", {"page": page})


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    company = get_company(request)
    results = {}
    if len(q) >= 2:
        if user_can(request.user, "crm", "view"):
            from apps.crm.models import Partner
            results["partners"] = Partner.objects.filter(company=company).filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))[:10]
        if user_can(request.user, "inventory", "view"):
            from apps.inventory.models import Product
            results["products"] = Product.objects.filter(company=company).filter(
                Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))[:10]
        if user_can(request.user, "sales", "view"):
            from apps.sales.models import Invoice
            results["invoices"] = Invoice.objects.filter(company=company).filter(
                Q(number__icontains=q) | Q(customer__name__icontains=q)).select_related("customer")[:10]
    return render(request, "core/search.html", {"q": q, "results": results})
