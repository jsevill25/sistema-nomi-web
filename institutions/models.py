from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Institution(models.Model):
	name = models.CharField("Nombre del liceo", max_length=160)
	legal_name = models.CharField("Razón social", max_length=200, blank=True)
	tax_id = models.CharField("RIF", max_length=24, blank=True)
	address = models.TextField("Dirección", blank=True)
	is_active = models.BooleanField("Activo", default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]
		verbose_name = "institución"
		verbose_name_plural = "instituciones"

	def __str__(self):
		return self.name


class InstitutionMembership(models.Model):
	class Role(models.TextChoices):
		ADMIN = "admin", "Administrador del liceo"
		OPERATOR = "operator", "Operador de nómina"
		VIEWER = "viewer", "Solo lectura"

	institution = models.ForeignKey(
		Institution, on_delete=models.CASCADE, related_name="memberships",
		verbose_name="Institución",
	)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="institution_memberships",
		verbose_name="Usuario",
	)
	role = models.CharField("Rol", max_length=16, choices=Role.choices, default=Role.OPERATOR)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["institution", "user"], name="unique_user_membership_per_institution"),
		]
		verbose_name = "membresía de institución"
		verbose_name_plural = "membresías de instituciones"

	def __str__(self):
		return f"{self.user} · {self.institution} ({self.get_role_display()})"


def institutions_for_user(user):
	if user.is_superuser:
		return Institution.objects.all()
	return Institution.objects.filter(memberships__user=user, is_active=True).distinct()


def operable_institutions_for_user(user):
	if user.is_superuser:
		return Institution.objects.filter(is_active=True)
	return Institution.objects.filter(
		memberships__user=user,
		memberships__role__in=[InstitutionMembership.Role.ADMIN, InstitutionMembership.Role.OPERATOR],
		is_active=True,
	).distinct()


def administrable_institutions_for_user(user):
	if user.is_superuser:
		return Institution.objects.filter(is_active=True)
	return Institution.objects.filter(
		memberships__user=user,
		memberships__role=InstitutionMembership.Role.ADMIN,
		is_active=True,
	).distinct()


class InstitutionPolicy(models.Model):
	institution = models.ForeignKey(
		Institution, on_delete=models.CASCADE, related_name="policies",
		verbose_name="Institución",
	)
	version = models.PositiveIntegerField("Versión")
	effective_from = models.DateField("Vigente desde")
	bcv_rate = models.DecimalField("Tasa BCV (Bs/USD)", max_digits=18, decimal_places=6)
	utility_days = models.PositiveSmallIntegerField("Días de utilidades", default=30)
	vacation_days = models.PositiveSmallIntegerField("Días de bono vacacional", default=15)
	vacation_days_per_year = models.PositiveSmallIntegerField(
		"Días adicionales por año de servicio", default=1,
	)
	cestaticket_usd = models.DecimalField(
		"Cestaticket (USD)", max_digits=12, decimal_places=2, default=40,
	)
	docente_scale_active = models.BooleanField("Escalafón docente activo", default=False)
	transport_is_salary = models.BooleanField("Transporte salarial", default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-effective_from", "-version"]
		constraints = [
			models.UniqueConstraint(
				fields=["institution", "version"], name="unique_institution_policy_version",
			),
			models.UniqueConstraint(
				fields=["institution", "effective_from"], name="unique_institution_policy_date",
			),
		]
		verbose_name = "configuración del liceo"
		verbose_name_plural = "configuraciones del liceo"

	def save(self, *args, **kwargs):
		if self.pk:
			original = InstitutionPolicy.objects.filter(pk=self.pk).first()
			if original and any(
				getattr(self, field.attname) != getattr(original, field.attname)
				for field in self._meta.concrete_fields if not field.primary_key
			):
				raise ValidationError("Las políticas versionadas son inmutables; crea una nueva versión.")
		super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		raise ValidationError("No se puede borrar una política versionada.")

	def clean(self):
		errors = {}
		if self.bcv_rate <= 0:
			errors["bcv_rate"] = "La tasa BCV debe ser mayor que cero."
		if self.utility_days < 30:
			errors["utility_days"] = "Las utilidades no pueden ser menores de 30 días."
		if self.vacation_days < 15:
			errors["vacation_days"] = "El bono vacacional base no puede ser menor de 15 días."
		if errors:
			raise ValidationError(errors)

	def __str__(self):
		return f"{self.institution} · v{self.version} · {self.effective_from}"

# Create your models here.
