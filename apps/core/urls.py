from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("connexion/", views.login_view, name="login"),
    path("deconnexion/", views.logout_view, name="logout"),
    path("applications/", views.catalog, name="catalog"),
    path("applications/<slug:code>/basculer/", views.module_toggle, name="module_toggle"),
    path("recherche/", views.search, name="search"),
    path("admin-erp/utilisateurs/", views.users, name="users"),
    path("admin-erp/utilisateurs/nouveau/", views.user_create, name="user_create"),
    path("admin-erp/utilisateurs/<int:pk>/", views.user_edit, name="user_edit"),
    path("admin-erp/roles/", views.roles, name="roles"),
    path("admin-erp/roles/<int:pk>/", views.role_edit, name="role_edit"),
    path("admin-erp/societe/", views.company_settings, name="company"),
    path("admin-erp/journal/", views.audit_log, name="audit"),
]
