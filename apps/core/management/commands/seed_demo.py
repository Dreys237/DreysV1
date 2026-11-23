from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.bootstrap import bootstrap
from apps.crm.models import Partner
from apps.inventory.models import Product, StockMovement
from apps.inventory.services import record_movement
from apps.sales.models import Invoice, InvoiceLine, Payment
from apps.sales.services import record_payment, validate_invoice


class Command(BaseCommand):
    help = "Crée des données DE DÉMONSTRATION (marquées DÉMO). Utiliser --purge pour les supprimer."

    def add_arguments(self, parser):
        parser.add_argument("--purge", action="store_true", help="Supprime toutes les données de démonstration.")

    @transaction.atomic
    def handle(self, *args, **options):
        company = bootstrap()
        if options["purge"]:
            Payment.objects.filter(invoice__is_demo=True).delete()
            InvoiceLine.objects.filter(invoice__is_demo=True).delete()
            Invoice.objects.filter(is_demo=True).delete()
            StockMovement.objects.filter(product__is_demo=True).delete()
            Product.objects.filter(is_demo=True).delete()
            Partner.objects.filter(is_demo=True).delete()
            self.stdout.write(self.style.SUCCESS("Données de démonstration supprimées."))
            return
        if Partner.objects.filter(is_demo=True).exists():
            self.stdout.write("Des données de démonstration existent déjà. Rien à faire.")
            return

        customers = [Partner.objects.create(company=company, kind="customer", is_demo=True, name=n, city=c)
                     for n, c in [("Boutique Plage Kribi (démo)", "Kribi"), ("Cliente Démo Douala", "Douala")]]
        Partner.objects.create(company=company, kind="prospect", is_demo=True, name="Prospect Démo Limbé", city="Limbé")
        Partner.objects.create(company=company, kind="supplier", is_demo=True, name="Fournisseur Fil & Co (démo)", city="Yaoundé")

        items = [("DEMO-001", "Maillot une pièce crochet", 25000, 12000, 4),
                 ("DEMO-002", "Bikini crochet", 20000, 9000, 5),
                 ("DEMO-003", "Paréo crochet", 15000, 6000, 3),
                 ("DEMO-004", "Chapeau de plage crochet", 8000, 3000, 2)]
        products = []
        for sku, name, price, cost, min_stock in items:
            p = Product.objects.create(company=company, sku=sku, name=name, sale_price=price,
                                       cost_price=cost, min_stock=min_stock, is_demo=True)
            record_movement(company, p, Decimal("10"), "in", reference="Stock initial (démo)")
            products.append(p)

        inv = Invoice.objects.create(company=company, customer=customers[0], is_demo=True,
                                     due_date=None)
        for p, qty in [(products[0], 2), (products[1], 3)]:
            InvoiceLine.objects.create(invoice=inv, product=p, description=p.name, quantity=qty,
                                       unit_price=p.sale_price, discount=0, tax_rate=company.default_tax_rate)
        inv.recompute()
        validate_invoice(inv.pk)
        record_payment(inv.pk, Decimal("50000"), "mtn", inv.date, "Paiement démo")

        draft = Invoice.objects.create(company=company, customer=customers[1], is_demo=True)
        InvoiceLine.objects.create(invoice=draft, product=products[2], description=products[2].name, quantity=1,
                                   unit_price=products[2].sale_price, discount=0, tax_rate=company.default_tax_rate)
        draft.recompute()
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
