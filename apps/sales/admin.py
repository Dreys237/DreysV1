from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment


class LineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "date", "status", "total_ttc")
    inlines = [LineInline]


admin.site.register(Payment)
