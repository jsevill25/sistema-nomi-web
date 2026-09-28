from django import forms

from institutions.forms import BootstrapModelForm
from institutions.models import operable_institutions_for_user

from .models import Employee


class EmployeeForm(BootstrapModelForm):
    class Meta:
        model = Employee
        fields = (
            "institution", "first_name", "last_name", "national_id", "job_title",
            "contract_type", "hire_date", "monthly_salary_usd", "hours_per_month",
            "hourly_rate_usd", "regular_bonus_usd", "transport_bonus_usd",
            "scale_bonus_usd", "is_active",
        )
        widgets = {"hire_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["institution"].queryset = operable_institutions_for_user(user)