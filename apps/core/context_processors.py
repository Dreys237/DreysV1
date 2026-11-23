from django.urls import reverse

from .models import Module
from .permissions import get_company, is_admin, user_can
from .services import get_notifications

MODULE_HOME = {
    "crm": "crm:partner_list",
    "sales": "sales:invoice_list",
    "inventory": "inventory:product_list",
}


def erp(request):
    if not request.user.is_authenticated:
        return {}
    nav = []
    for module in Module.objects.filter(is_active=True, is_implemented=True):
        if module.code in MODULE_HOME and user_can(request.user, module.code, "view"):
            nav.append({"module": module, "url": reverse(MODULE_HOME[module.code])})
    company = get_company(request)
    return {
        "nav_modules": nav,
        "current_company": company,
        "is_erp_admin": is_admin(request.user),
        "notifications": get_notifications(request.user, company),
    }
