from django.core.exceptions import ValidationError
from django.db import models

from institutions.models import Institution


class Employee(models.Model):
	class ContractType(models.TextChoices):
		ADMINISTRATIVE = "administrative", "Administrativo"
		WORKER = "worker", "Obrero"
		HOURLY_TEACHER = "hourly_teacher", "Profesor por horas / cátedra"
		FULL_TIME_TEACHER = "full_time_teacher", "Profesor tiempo completo"

	institution = models.ForeignKey(
		Institution, on_delete=models.PROTECT, related_name="employees",
		verbose_name="Institución",
	)
	first_name = models.CharField("Nombres", max_length=100)
	last_name = models.CharField("Apellidos", max_length=100)
	national_id = models.CharField("Cédula", max_length=24)
	job_title = models.CharField("Cargo", max_length=120)
	contract_type = models.CharField(
		"Tipo de contrato", max_length=24, choices=ContractType.choices,
	)
	hire_date = models.DateField("Fecha de ingreso")
	monthly_salary_usd = models.DecimalField(
		"Sueldo mensual (USD)", max_digits=12, decimal_places=2, default=0,
	)
	hours_per_month = models.DecimalField(
		"Horas dictadas al mes", max_digits=8, decimal_places=2, default=0,
	)
	hourly_rate_usd = models.DecimalField(
		"Valor hora (USD)", max_digits=12, decimal_places=2, default=0,
	)
	regular_bonus_usd = models.DecimalField(
		"Bonos regulares salariales (USD)", max_digits=12, decimal_places=2, default=0,
	)
	transport_bonus_usd = models.DecimalField(
		"Bono de transporte (USD)", max_digits=12, decimal_places=2, default=0,
	)
	scale_bonus_usd = models.DecimalField(
		"Bono de escalafón (USD)", max_digits=12, decimal_places=2, default=0,
	)
	is_active = models.BooleanField("Activo", default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["last_name", "first_name"]
		constraints = [
			models.UniqueConstraint(
				fields=["institution", "national_id"], name="unique_employee_id_per_institution",
			),
		]
		verbose_name = "empleado"
		verbose_name_plural = "empleados"

	def clean(self):
		errors = {}
		if self.contract_type == self.ContractType.HOURLY_TEACHER:
			if self.hours_per_month <= 0:
				errors["hours_per_month"] = "Indica las horas dictadas del mes."
			if self.hourly_rate_usd <= 0:
				errors["hourly_rate_usd"] = "El valor hora debe ser mayor que cero."
		elif self.monthly_salary_usd <= 0:
			errors["monthly_salary_usd"] = "El sueldo mensual debe ser mayor que cero."
		if errors:
			raise ValidationError(errors)

	@property
	def full_name(self):
		return f"{self.first_name} {self.last_name}"

	def __str__(self):
		return self.full_name

# Create your models here.
