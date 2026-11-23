"""Contrôle d'accès (RBAC) appliqué côté serveur."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import Company, Module, Profile, RolePermission

ACTIONS = ("view", "create", "edit", "validate", "cancel", "delete", "export")
ADMIN_ROLE_CODES = ("super_admin", "admin")


def get_profile(user):
    try:
        return user.profile
    except Profile.DoesNotExist:
        return Profile.objects.create(user=user, company=Company.objects.first())


def is_admin(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    role = get_profile(user).role
    return bool(role and role.code in ADMIN_ROLE_CODES)


def get_company(request):
    if not hasattr(request, "_company"):
        company = get_profile(request.user).company if request.user.is_authenticated else None
        request._company = company or Company.objects.first()
    return request._company


def module_is_usable(code):
    return Module.objects.filter(code=code, is_active=True, is_implemented=True).exists()


def user_can(user, code, action="view"):
    if not user.is_authenticated or not user.is_active:
        return False
    if not module_is_usable(code):
        return False  # un module désactivé n'est plus accessible, même pour un administrateur
    if is_admin(user):
        return True
    role_id = get_profile(user).role_id
    if not role_id:
        return False
    return RolePermission.objects.filter(
        role_id=role_id, module__code=code, **{f"can_{action}": True}
    ).exists()


def module_required(code, action="view"):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not user_can(request.user, code, action):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper
