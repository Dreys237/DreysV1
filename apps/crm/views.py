from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import get_company, module_required
from apps.core.services import audit
from apps.core.utils import paginate

from .forms import InteractionForm, PartnerForm
from .models import Partner


@module_required("crm", "view")
def partner_list(request):
    qs = Partner.objects.filter(company=get_company(request))
    kind = request.GET.get("kind", "")
    q = request.GET.get("q", "").strip()
    if kind in dict(Partner.KINDS):
        qs = qs.filter(kind=kind)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    return render(request, "crm/partner_list.html", {
        "page": paginate(request, qs), "kind": kind, "q": q, "kinds": Partner.KINDS})


@module_required("crm", "create")
def partner_create(request):
    company = get_company(request)
    form = PartnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        partner = form.save(commit=False)
        partner.company, partner.created_by = company, request.user
        partner.save()
        audit(request.user, company, "crm", "Contact créé", partner.name)
        messages.success(request, f"« {partner.name} » enregistré.")
        return redirect("crm:partner_detail", pk=partner.pk)
    return render(request, "form.html", {"form": form, "title": "Nouveau contact", "cancel_url": "crm:partner_list"})


@module_required("crm", "view")
def partner_detail(request, pk):
    partner = get_object_or_404(Partner, pk=pk, company=get_company(request))
    return render(request, "crm/partner_detail.html", {
        "partner": partner, "interaction_form": InteractionForm(),
        "interactions": partner.interactions.select_related("user")[:50]})


@module_required("crm", "edit")
def partner_edit(request, pk):
    company = get_company(request)
    partner = get_object_or_404(Partner, pk=pk, company=company)
    form = PartnerForm(request.POST or None, instance=partner)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, company, "crm", "Contact modifié", partner.name)
        messages.success(request, "Modifications enregistrées.")
        return redirect("crm:partner_detail", pk=partner.pk)
    return render(request, "form.html", {"form": form, "title": f"Modifier {partner.name}",
                                         "cancel_url": "crm:partner_list"})


@module_required("crm", "edit")
@require_POST
def partner_convert(request, pk):
    company = get_company(request)
    partner = get_object_or_404(Partner, pk=pk, company=company, kind="prospect")
    partner.kind = "customer"
    partner.save(update_fields=["kind"])
    audit(request.user, company, "crm", "Prospect converti en client", partner.name)
    messages.success(request, f"« {partner.name} » est maintenant client.")
    return redirect("crm:partner_detail", pk=partner.pk)


@module_required("crm", "create")
@require_POST
def interaction_add(request, pk):
    partner = get_object_or_404(Partner, pk=pk, company=get_company(request))
    form = InteractionForm(request.POST)
    if form.is_valid():
        it = form.save(commit=False)
        it.partner, it.user = partner, request.user
        it.save()
        messages.success(request, "Échange ajouté à l'historique.")
    else:
        messages.error(request, "Le détail de l'échange est obligatoire.")
    return redirect("crm:partner_detail", pk=partner.pk)


@module_required("crm", "delete")
@require_POST
def partner_delete(request, pk):
    company = get_company(request)
    partner = get_object_or_404(Partner, pk=pk, company=company)
    try:
        name = partner.name
        partner.delete()
    except ProtectedError:
        messages.error(request, "Suppression impossible : des documents (factures) sont liés à ce contact.")
        return redirect("crm:partner_detail", pk=pk)
    audit(request.user, company, "crm", "Contact supprimé", name)
    messages.success(request, f"« {name} » supprimé.")
    return redirect("crm:partner_list")
