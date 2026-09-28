from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from institutions.models import institutions_for_user, operable_institutions_for_user

from .forms import EmployeeForm
from .models import Employee


@login_required
def employee_list(request):
    employees = Employee.objects.select_related("institution").filter(
        institution__in=institutions_for_user(request.user),
    )
    institution_id = request.GET.get("institution")
    if institution_id:
        employees = employees.filter(institution_id=institution_id)
    return render(request, "employees/list.html", {
        "employees": employees,
        "institutions": institutions_for_user(request.user),
        "selected_institution": institution_id,
        "editable_institution_ids": set(
            operable_institutions_for_user(request.user).values_list("pk", flat=True)
        ),
        "can_operate": operable_institutions_for_user(request.user).exists(),
    })


@login_required
def employee_create(request):
    form = EmployeeForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Empleado agregado al registro.")
        return redirect("employees")
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Nuevo empleado", "eyebrow": "Equipo",
    })


@login_required
def employee_edit(request, pk):
    employee = get_object_or_404(
        Employee.objects.filter(institution__in=operable_institutions_for_user(request.user)),
        pk=pk,
    )
    form = EmployeeForm(request.POST or None, instance=employee, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ficha del empleado actualizada.")
        return redirect("employees")
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Editar empleado", "eyebrow": "Equipo",
    })
