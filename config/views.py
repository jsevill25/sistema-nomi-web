from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from employees.models import Employee
from institutions.models import (
    InstitutionPolicy, administrable_institutions_for_user,
    institutions_for_user, operable_institutions_for_user,
)
from payroll.models import PayrollRun


@login_required
def dashboard(request):
    institutions = institutions_for_user(request.user)
    institution_count = institutions.count()
    employee_count = Employee.objects.filter(institution__in=institutions, is_active=True).count()
    latest_runs = PayrollRun.objects.filter(
        institution__in=institutions,
    ).select_related("institution").prefetch_related("results")[:5]
    totals = PayrollRun.objects.filter(institution__in=institutions).order_by("-period_end").first()
    last_total = totals.results.aggregate(total=Sum("normal_monthly_bs"))["total"] if totals else 0
    return render(request, "dashboard.html", {
        "institution_count": institution_count,
        "employee_count": employee_count,
        "policy_count": InstitutionPolicy.objects.filter(institution__in=institutions).count(),
        "can_operate": operable_institutions_for_user(request.user).exists(),
        "can_administer": administrable_institutions_for_user(request.user).exists(),
        "latest_runs": latest_runs,
        "last_total": last_total or 0,
        "needs_setup": institution_count == 0 or not InstitutionPolicy.objects.filter(
            institution__in=institutions,
        ).exists(),
    })