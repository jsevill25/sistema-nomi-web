from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import InstitutionForm, InstitutionPolicyForm
from .models import (
    Institution, InstitutionMembership, InstitutionPolicy,
    administrable_institutions_for_user, institutions_for_user,
)


@login_required
def institution_list(request):
    institutions = list(institutions_for_user(request.user))
    policies = InstitutionPolicy.objects.filter(
        institution__in=institutions,
        effective_from__lte=timezone.localdate(),
    ).order_by("institution_id", "-effective_from", "-version")
    current_policies = {}
    for policy in policies:
        current_policies.setdefault(policy.institution_id, policy)
    for institution in institutions:
        institution.current_policy = current_policies.get(institution.pk)
    return render(request, "institutions/list.html", {
        "institutions": institutions,
        "can_create_institution": True,
        "editable_institution_ids": set(
            administrable_institutions_for_user(request.user).values_list("pk", flat=True)
        ),
        "administrable_institution_ids": set(
            administrable_institutions_for_user(request.user).values_list("pk", flat=True)
        ),
    })


@login_required
def institution_create(request):
    form = InstitutionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        institution = form.save()
        InstitutionMembership.objects.create(
            institution=institution, user=request.user, role=InstitutionMembership.Role.ADMIN,
        )
        messages.success(request, "Institución creada. Agrega ahora su configuración vigente.")
        return redirect("institution_policy_create")
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Nueva institución", "eyebrow": "Organización",
    })


@login_required
def institution_edit(request, pk):
    institution = get_object_or_404(administrable_institutions_for_user(request.user), pk=pk)
    form = InstitutionForm(request.POST or None, instance=institution)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos de la institución actualizados.")
        return redirect("institutions")
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Editar institución", "eyebrow": "Organización",
    })


@login_required
def institution_policy_create(request):
    form = InstitutionPolicyForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configuración institucional guardada.")
        return redirect("institutions")
    return render(request, "shared/form_page.html", {
        "form": form, "title": "Configuración del liceo", "eyebrow": "Reglas por institución",
    })
