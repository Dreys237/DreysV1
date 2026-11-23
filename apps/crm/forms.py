from apps.core.forms import StyledModelForm

from .models import Interaction, Partner


class PartnerForm(StyledModelForm):
    class Meta:
        model = Partner
        fields = ["kind", "name", "email", "phone", "address", "city", "tax_id", "notes"]


class InteractionForm(StyledModelForm):
    class Meta:
        model = Interaction
        fields = ["kind", "text"]
