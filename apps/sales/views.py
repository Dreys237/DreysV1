from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permissions import get_company, module_required
from apps.core.services import audit
from apps.core.utils import paginate

from .forms import InvoiceForm, PaymentForm, line_formset
from .models import Invoice
from .services import cancel_invoice, record_payment, validate_invoice


def _get_invoice(request, pk):
    return get_object_or_404(Invoice.objects.select_related("customer"), pk=pk, company=get_company(request))


@module_required("sales", "view")
def invoice_list(request):
    qs = Invoice.objects.filter(company=get_company(request)).select_related("customer")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if status == "overdue":
        qs = qs.filter(status="validated", due_date__lt=timezone.localdate())
    elif status in dict(Invoice.STATUSES):
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q))
    return render(request, "sales/invoice_list.html", {
        "page": paginate(request, qs), "status": status, "q": q, "statuses": Invoice.STATUSES})


def _edit(request, invoice=None):
    company = get_company(request)
    FormSet = line_formset(extra=4 if invoice is None else 2)
    form = InvoiceForm(request.POST or None, instance=invoice, company=company)
    formset = FormSet(request.POST or None, instance=invoice or Invoice(), form_kwargs={"company": company})
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        inv = form.save(commit=False)
        if invoice is None:
            inv.company, inv.created_by = company, request.user
        inv.save()
        formset.instance = inv
        formset.save()
        inv.recompute()
        audit(request.user, company, "sales", "Facture enregistrée (brouillon)", f"#{inv.pk}")
        messages.success(request, "Brouillon enregistré. Vérifiez-le puis validez-le.")
        return redirect("sales:invoice_detail", pk=inv.pk)
    title = "Nouvelle facture" if invoice is None else f"Modifier le brouillon #{invoice.pk}"
    return render(request, "sales/invoice_form.html", {"form": form, "formset": formset, "title": title})


@module_required("sales", "create")
def invoice_create(request):
    return _edit(request)


@module_required("sales", "edit")
def invoice_edit(request, pk):
    invoice = _get_invoice(request, pk)
    if invoice.status != "draft":
        messages.error(request, "Une facture validée n'est plus modifiable. Annulez-la si nécessaire.")
        return redirect("sales:invoice_detail", pk=pk)
    return _edit(request, invoice)


@module_required("sales", "view")
def invoice_detail(request, pk):
    invoice = _get_invoice(request, pk)
    return render(request, "sales/invoice_detail.html", {
        "invoice": invoice, "lines": invoice.lines.select_related("product"),
        "payments": invoice.payments.all(), "payment_form": PaymentForm(
            initial={"date": timezone.localdate(), "amount": invoice.balance})})


@module_required("sales", "validate")
@require_POST
def invoice_validate(request, pk):
    invoice = _get_invoice(request, pk)
    try:
        validate_invoice(invoice.pk, request.user)
        messages.success(request, "Facture validée : numéro attribué et stock mis à jour.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("sales:invoice_detail", pk=pk)


@module_required("sales", "cancel")
@require_POST
def invoice_cancel(request, pk):
    invoice = _get_invoice(request, pk)
    try:
        cancel_invoice(invoice.pk, request.user)
        messages.success(request, "Facture annulée et stock rétabli.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("sales:invoice_detail", pk=pk)


@module_required("sales", "edit")
@require_POST
def payment_add(request, pk):
    invoice = _get_invoice(request, pk)
    form = PaymentForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            record_payment(invoice.pk, d["amount"], d["method"], d["date"], d["reference"], request.user)
            messages.success(request, "Paiement enregistré.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Paiement invalide : vérifiez les champs.")
    return redirect("sales:invoice_detail", pk=pk)


@module_required("sales", "delete")
@require_POST
def invoice_delete(request, pk):
    invoice = _get_invoice(request, pk)
    if invoice.status != "draft":
        messages.error(request, "Seuls les brouillons peuvent être supprimés. Annulez les factures validées.")
        return redirect("sales:invoice_detail", pk=pk)
    audit(request.user, get_company(request), "sales", "Brouillon supprimé", f"#{invoice.pk}")
    invoice.delete()
    messages.success(request, "Brouillon supprimé.")
    return redirect("sales:invoice_list")
