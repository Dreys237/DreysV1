from django.core.management.base import BaseCommand

from apps.core.bootstrap import bootstrap


class Command(BaseCommand):
    help = "Initialise les modules, les rôles et la société par défaut (idempotent)."

    def handle(self, *args, **options):
        company = bootstrap()
        self.stdout.write(self.style.SUCCESS(f"ERP initialisé pour « {company.name} »."))
