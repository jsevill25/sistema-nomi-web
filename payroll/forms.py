from django import forms

from institutions.forms import BootstrapModelForm
from institutions.models import operable_institutions_for_user

from .models import PayrollRun


class PayrollRunForm(BootstrapModelForm):
    class Meta:
        model = PayrollRun
        fields = ("institution", "period_start", "period_end")
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["institution"].queryset = operable_institutions_for_user(user)