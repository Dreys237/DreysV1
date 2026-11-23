from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.core.bootstrap import bootstrap
from apps.core.models import Module, Profile, Role
from apps.crm.models import Partner
from apps.inventory.models import Product
from apps.inventory.services import current_stock, record_movement
from apps.sales.models import Invoice, InvoiceLine
from apps.sales.services import cancel_invoice, record_payment, validate_invoice

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.company = bootstrap()
        self.admin = User.objects.create_superuser("boss", "b@x.cm", "Str0ng-pass-123")
        self.customer = Partner.objects.create(company=self.company, kind="customer", name="Client A")
        self.product = Product.objects.create(company=self.company, sku="P1", name="Maillot",
                                              sale_price=Decimal("25000"), cost_price=Decimal("12000"))
        record_movement(self.company, self.product, Decimal("10"), "in")

    def make_user(self, username, role_code):
        u = User.objects.create_user(username, password="Str0ng-pass-123")
        Profile.objects.update_or_create(user=u, defaults={"company": self.company,
                                                           "role": Role.objects.get(code=role_code)})
        return u

    def invoice(self, qty="2", tax="0"):
        inv = Invoice.objects.create(company=self.company, customer=self.customer)
        InvoiceLine.objects.create(invoice=inv, product=self.product, description="Maillot",
                                   quantity=Decimal(qty), unit_price=Decimal("25000"),
                                   discount=Decimal("0"), tax_rate=Decimal(tax))
        inv.recompute()
        return inv


class AuthTests(Base):
    def test_login_required(self):
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("connexion", r["Location"])

    def test_login_logout_flow(self):
        r = self.client.post(reverse("core:login"), {"username": "boss", "password": "Str0ng-pass-123"})
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
        self.client.post(reverse("core:logout"))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 302)

    def test_login_throttling(self):
        for _ in range(5):
            self.client.post(reverse("core:login"), {"username": "boss", "password": "bad"})
        r = self.client.post(reverse("core:login"), {"username": "boss", "password": "Str0ng-pass-123"})
        self.assertEqual(r.status_code, 200)  # reste bloqué malgré le bon mot de passe


class PermissionTests(Base):
    def test_reader_cannot_create_server_side(self):
        self.make_user("lect", "lecteur")
        self.client.login(username="lect", password="Str0ng-pass-123")
        self.assertEqual(self.client.get(reverse("crm:partner_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("crm:partner_create")).status_code, 403)
        r = self.client.post(reverse("crm:partner_create"), {"kind": "customer", "name": "X"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Partner.objects.filter(name="X").exists())

    def test_non_admin_cannot_access_admin_pages(self):
        self.make_user("com", "commercial")
        self.client.login(username="com", password="Str0ng-pass-123")
        self.assertEqual(self.client.get(reverse("core:users")).status_code, 403)

    def test_commercial_cannot_validate_invoice(self):
        self.make_user("com", "commercial")
        inv = self.invoice()
        self.client.login(username="com", password="Str0ng-pass-123")
        self.assertEqual(self.client.post(reverse("sales:invoice_validate", args=[inv.pk])).status_code, 403)

    def test_disabled_module_blocks_everyone(self):
        self.client.login(username="boss", password="Str0ng-pass-123")
        self.assertEqual(self.client.get(reverse("sales:invoice_list")).status_code, 200)
        self.client.post(reverse("core:module_toggle", args=["sales"]))  # désactivation réelle via l'interface
        self.assertFalse(Module.objects.get(code="sales").is_active)
        self.assertEqual(self.client.get(reverse("sales:invoice_list")).status_code, 403)

    def test_cannot_disable_module_with_dependants(self):
        self.client.login(username="boss", password="Str0ng-pass-123")
        self.client.post(reverse("core:module_toggle", args=["crm"]))
        self.assertTrue(Module.objects.get(code="crm").is_active)

    def test_company_isolation(self):
        from apps.core.models import Company
        other = Company.objects.create(name="Autre société")
        p = Partner.objects.create(company=other, kind="customer", name="Secret")
        self.client.login(username="boss", password="Str0ng-pass-123")
        self.assertEqual(self.client.get(reverse("crm:partner_detail", args=[p.pk])).status_code, 404)


class BusinessTests(Base):
    def test_totals_use_decimal(self):
        inv = self.invoice(qty="3", tax="10")
        self.assertEqual(inv.total_ht, Decimal("75000.00"))
        self.assertEqual(inv.total_tax, Decimal("7500.00"))
        self.assertEqual(inv.total_ttc, Decimal("82500.00"))

    def test_validate_moves_stock_and_numbers(self):
        inv = validate_invoice(self.invoice(qty="4").pk)
        self.assertEqual(current_stock(self.product), Decimal("6"))
        self.assertRegex(inv.number, r"^FAC-\d{4}-00001$")
        second = validate_invoice(self.invoice(qty="1").pk)
        self.assertTrue(second.number.endswith("00002"))

    def test_negative_stock_blocked_and_rolled_back(self):
        inv = self.invoice(qty="50")
        with self.assertRaises(ValidationError):
            validate_invoice(inv.pk)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "draft")
        self.assertIsNone(inv.number)
        self.assertEqual(current_stock(self.product), Decimal("10"))

    def test_negative_stock_allowed_by_setting(self):
        self.company.allow_negative_stock = True
        self.company.save()
        validate_invoice(self.invoice(qty="50").pk)
        self.assertEqual(current_stock(self.product), Decimal("-40"))

    def test_cancel_restores_stock_only_without_payment(self):
        inv = validate_invoice(self.invoice(qty="2").pk)
        record_payment(inv.pk, Decimal("1000"), "cash", inv.date)
        with self.assertRaises(ValidationError):
            cancel_invoice(inv.pk)
        inv2 = validate_invoice(self.invoice(qty="1").pk)
        cancel_invoice(inv2.pk)
        self.assertEqual(current_stock(self.product), Decimal("8"))

    def test_payments_update_status_and_reject_overpayment(self):
        inv = validate_invoice(self.invoice(qty="1").pk)
        with self.assertRaises(ValidationError):
            record_payment(inv.pk, Decimal("30000"), "cash", inv.date)
        record_payment(inv.pk, Decimal("10000"), "mtn", inv.date)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "validated")
        self.assertEqual(inv.balance, Decimal("15000.00"))
        record_payment(inv.pk, Decimal("15000"), "bank", inv.date)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "paid")

    def test_validated_invoice_not_editable_or_deletable(self):
        inv = validate_invoice(self.invoice().pk)
        self.client.login(username="boss", password="Str0ng-pass-123")
        self.client.post(reverse("sales:invoice_delete", args=[inv.pk]))
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())
        self.assertEqual(self.client.get(reverse("sales:invoice_edit", args=[inv.pk])).status_code, 302)


class UiSmokeTests(Base):
    def test_all_main_pages_render(self):
        self.client.login(username="boss", password="Str0ng-pass-123")
        inv = validate_invoice(self.invoice().pk)
        for name, args in [("core:dashboard", []), ("core:catalog", []), ("core:users", []),
                           ("core:user_create", []), ("core:roles", []), ("core:company", []),
                           ("core:audit", []), ("core:search", []), ("crm:partner_list", []),
                           ("crm:partner_create", []), ("crm:partner_detail", [self.customer.pk]),
                           ("inventory:product_list", []), ("inventory:product_create", []),
                           ("inventory:product_detail", [self.product.pk]),
                           ("inventory:movement_list", []), ("inventory:movement_create", []),
                           ("sales:invoice_list", []), ("sales:invoice_create", []),
                           ("sales:invoice_detail", [inv.pk])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)
        role = Role.objects.get(code="commercial")
        self.assertEqual(self.client.get(reverse("core:role_edit", args=[role.pk])).status_code, 200)

    def test_create_invoice_through_form_persists(self):
        self.client.login(username="boss", password="Str0ng-pass-123")
        data = {"customer": self.customer.pk, "date": "2026-11-23", "due_date": "", "notes": "",
                "lines-TOTAL_FORMS": "4", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-product": self.product.pk, "lines-0-description": "", "lines-0-quantity": "2",
                "lines-0-unit_price": "", "lines-0-discount": "", "lines-0-tax_rate": ""}
        for i in (1, 2, 3):
            for f in ("product", "description", "quantity", "unit_price", "discount", "tax_rate"):
                data[f"lines-{i}-{f}"] = ""
        r = self.client.post(reverse("sales:invoice_create"), data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["formset"].errors)
        inv = Invoice.objects.latest("id")
        self.assertEqual(inv.lines.count(), 1)
        self.assertEqual(inv.total_ttc, Decimal("50000.00"))  # prix repris du produit, taxe 0 par défaut

    def test_user_creation_and_role(self):
        self.client.login(username="boss", password="Str0ng-pass-123")
        role = Role.objects.get(code="caissier")
        r = self.client.post(reverse("core:user_create"), {
            "username": "caisse1", "first_name": "A", "last_name": "B", "email": "", "role": role.pk,
            "is_active": "on", "password1": "Another-Str0ng-1", "password2": "Another-Str0ng-1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.get(username="caisse1").profile.role, role)
        weak = self.client.post(reverse("core:user_create"), {
            "username": "x2", "password1": "123", "password2": "123"})
        self.assertEqual(weak.status_code, 200)
        self.assertFalse(User.objects.filter(username="x2").exists())
