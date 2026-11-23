from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Company, Role

User = get_user_model()


def _style(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = "check"
        else:
            widget.attrs["class"] = (widget.attrs.get("class", "") + " input").strip()


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class CompanyForm(StyledModelForm):
    class Meta:
        model = Company
        fields = ["name", "legal_name", "tax_id", "address", "city", "country", "phone", "email",
                  "currency", "default_tax_rate", "allow_negative_stock"]


class UserForm(StyledForm):
    username = forms.CharField(label="Identifiant", max_length=150)
    first_name = forms.CharField(label="Prénom", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)
    role = forms.ModelChoiceField(label="Rôle", queryset=Role.objects.all(), required=False)
    is_active = forms.BooleanField(label="Compte actif", required=False, initial=True)
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None:
            initial = kwargs.setdefault("initial", {})
            initial.update(username=instance.username, first_name=instance.first_name,
                           last_name=instance.last_name, email=instance.email,
                           is_active=instance.is_active, role=instance.profile.role_id
                           if hasattr(instance, "profile") else None)
        super().__init__(*args, **kwargs)
        if instance is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Laisser vide pour ne pas changer."

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return username

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Les mots de passe ne correspondent pas.")
            else:
                try:
                    validate_password(p1, self.instance)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return data

    def save(self, company):
        from .permissions import get_profile
        d = self.cleaned_data
        user = self.instance or User()
        user.username, user.first_name, user.last_name = d["username"], d["first_name"], d["last_name"]
        user.email, user.is_active = d["email"], d["is_active"]
        if d.get("password1"):
            user.set_password(d["password1"])
        user.save()
        profile = get_profile(user)
        profile.role = d["role"]
        if profile.company_id is None:
            profile.company = company
        profile.save()
        return user
