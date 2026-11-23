"""Initialisation du catalogue de modules, des rôles et de la société par défaut."""
from .models import Company, Module, Role, RolePermission

# code, nom, icône, description, développé ?, dépendances, ordre
MODULES = [
    ("crm", "CRM", "👥", "Prospects, clients, fournisseurs et historique des échanges.", True, [], 10),
    ("inventory", "Inventaire", "📦", "Produits, entrepôts, mouvements et valorisation du stock.", True, [], 20),
    ("sales", "Ventes & Facturation", "🧾", "Factures, paiements et suivi des créances.", True, ["crm", "inventory"], 30),
    ("purchases", "Achats", "🛒", "Fournisseurs, commandes et réceptions.", False, ["inventory"], 40),
    ("accounting", "Comptabilité", "📒", "SYSCOHADA révisé : journaux, écritures, états.", False, [], 50),
    ("hr", "Ressources humaines", "🧑‍💼", "Employés, contrats, congés, présences.", False, [], 60),
    ("payroll", "Paie", "💵", "Bulletins de paie configurables.", False, ["hr"], 70),
    ("projects", "Projets", "🗂️", "Projets, tâches, suivi du temps.", False, [], 80),
    ("manufacturing", "Fabrication", "🏭", "Nomenclatures et ordres de fabrication.", False, ["inventory"], 90),
    ("pos", "Point de vente", "🏪", "Interface de caisse.", False, ["inventory"], 100),
]

ROLES = [
    ("super_admin", "Super administrateur"), ("admin", "Administrateur"),
    ("dg", "Directeur général"), ("dir_fin", "Directeur financier"),
    ("comptable", "Comptable"), ("resp_commercial", "Responsable commercial"),
    ("commercial", "Commercial"), ("resp_achats", "Responsable achats"),
    ("gest_stock", "Gestionnaire de stock"), ("resp_rh", "Responsable RH"),
    ("gest_paie", "Gestionnaire de paie"), ("chef_projet", "Chef de projet"),
    ("technicien", "Technicien"), ("employe", "Employé"),
    ("caissier", "Caissier"), ("auditeur", "Auditeur"), ("lecteur", "Lecteur"),
]

ALL = {"view", "create", "edit", "validate", "cancel", "delete", "export"}
READ = {"view"}

# Préréglages de départ : entièrement modifiables dans l'écran « Rôles & permissions ».
PRESETS = {
    "dg": {"crm": READ | {"export"}, "sales": READ | {"export", "validate"}, "inventory": READ | {"export"}},
    "dir_fin": {"crm": READ, "sales": READ | {"validate", "cancel", "export"}, "inventory": READ},
    "comptable": {"crm": READ, "sales": READ | {"validate", "export"}, "inventory": READ},
    "resp_commercial": {"crm": ALL, "sales": ALL - {"delete"}, "inventory": READ},
    "commercial": {"crm": {"view", "create", "edit"}, "sales": {"view", "create", "edit"}, "inventory": READ},
    "resp_achats": {"inventory": READ | {"export"}},
    "gest_stock": {"inventory": ALL, "sales": READ},
    "caissier": {"crm": READ, "sales": {"view", "create"}, "inventory": READ},
    "auditeur": {"crm": READ | {"export"}, "sales": READ | {"export"}, "inventory": READ | {"export"}},
    "lecteur": {"crm": READ, "sales": READ, "inventory": READ},
}


def bootstrap():
    modules = {}
    for code, name, icon, desc, implemented, _deps, seq in MODULES:
        module, created = Module.objects.get_or_create(code=code, defaults={
            "name": name, "icon": icon, "description": desc, "sequence": seq,
            "is_implemented": implemented, "is_active": implemented,
        })
        if not created:
            Module.objects.filter(pk=module.pk).update(
                name=name, icon=icon, description=desc, sequence=seq, is_implemented=implemented)
        modules[code] = module
    for code, _n, _i, _d, _impl, deps, _s in MODULES:
        modules[code].depends_on.set([modules[d] for d in deps])

    for code, name in ROLES:
        role, created = Role.objects.get_or_create(code=code, defaults={"name": name})
        if created:  # on n'écrase jamais des permissions déjà modifiées
            for mod_code, actions in PRESETS.get(code, {}).items():
                RolePermission.objects.create(
                    role=role, module=modules[mod_code], **{f"can_{a}": True for a in actions})

    company = Company.objects.first()
    if company is None:
        company = Company.objects.create(name="DREY'S COMPAGNIE", legal_name="DREY'S COMPAGNIE")
    from apps.inventory.services import get_default_warehouse
    get_default_warehouse(company)
    return company
