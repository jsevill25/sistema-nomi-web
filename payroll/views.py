from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from institutions.models import institutions_for_user, operable_institutions_for_user

from .forms import PayrollRunForm
from .models import PayrollRun
from .services import create_payroll_run, severance_for_result


@login_required
def payroll_list(request):
    runs = PayrollRun.objects.filter(
        institution__in=institutions_for_user(request.user),
    ).select_related("institution", "policy").prefetch_related("results")
    return render(request, "payroll/list.html", {
        "runs": runs,
        "can_operate": operable_institutions_for_user(request.user).exists(),
    })


@login_required
def payroll_create(request):
    form = PayrollRunForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            run = create_payroll_run(
                values["institution"], values["period_start"], values["period_end"], request.user,
            )
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(request, "Nómina calculada y guardada con sus parámetros de origen.")
            return redirect("payroll_detail", pk=run.pk)
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Procesar nómina", "eyebrow": "Cálculo mensual",
    })


@login_required
def payroll_detail(request, pk):
    run = get_object_or_404(
        PayrollRun.objects.select_related("institution", "policy", "legal_rules")
        .prefetch_related("results__employee"),
        pk=pk,
        institution__in=institutions_for_user(request.user),
    )
    rows = [(result, severance_for_result(result)) for result in run.results.all()]
    return render(request, "payroll/detail.html", {"run": run, "rows": rows})
