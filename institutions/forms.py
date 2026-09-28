from django import forms

from .models import Institution, InstitutionPolicy, administrable_institutions_for_user


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()


class InstitutionForm(BootstrapModelForm):
    class Meta:
        model = Institution
        fields = ("name", "legal_name", "tax_id", "address", "is_active")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class InstitutionPolicyForm(BootstrapModelForm):
    class Meta:
        model = InstitutionPolicy
        fields = (
            "institution", "version", "effective_from", "bcv_rate", "utility_days",
            "vacation_days", "vacation_days_per_year", "cestaticket_usd",
            "docente_scale_active", "transport_is_salary",
        )
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["institution"].queryset = administrable_institutions_for_user(user)