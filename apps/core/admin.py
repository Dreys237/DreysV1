from django.contrib import admin

from .models import AuditLog, Company, Module, Profile, Role, RolePermission

admin.site.register([Company, Module, Role, RolePermission, Profile])


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created", "user", "module", "action", "object_repr")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
