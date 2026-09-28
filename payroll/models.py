from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from employees.models import Employee
from institutions.models import Institution, InstitutionPolicy


class LegalRuleSet(models.Model):
	"""Effective-dated global contribution parameters, editable in Django admin."""

	name = models.CharField("Nombre de la versión legal", max_length=120)
	effective_from = models.DateField("Vigente desde")
	minimum_monthly_salary_bs = models.DecimalField(
		"Salario mínimo mensual de referencia (Bs)", max_digits=16, decimal_places=2,
	)
	ivss_employee_rate = models.DecimalField(
		"Tasa IVSS trabajador", max_digits=7, decimal_places=6,
		help_text="Proporción decimal; por ejemplo, 0.04 equivale a 4 %.",
	)
	ivss_cap_minimum_wages = models.DecimalField(
		"Tope IVSS (salarios mínimos)", max_digits=7, decimal_places=2,
	)
	faov_employee_rate = models.DecimalField(
		"Tasa FAOV trabajador", max_digits=7, decimal_places=6,
		help_text="Proporción decimal; por ejemplo, 0.01 equivale a 1 %.",
	)
	unemployment_employee_rate = models.DecimalField(
		"Tasa paro forzoso trabajador", max_digits=7, decimal_places=6,
		help_text="Proporción decimal; por ejemplo, 0.005 equivale a 0,5 %.",
	)
	unemployment_cap_minimum_wages = models.DecimalField(
		"Tope paro forzoso (salarios mínimos)", max_digits=7, decimal_places=2,
	)
	additional_benefit_days_per_year = models.PositiveSmallIntegerField(
		"Días adicionales de prestaciones por año", default=2,
	)
	additional_benefit_days_cap = models.PositiveSmallIntegerField(
		"Tope acumulado de días adicionales", default=30,
	)

	class Meta:
		ordering = ["-effective_from"]
		constraints = [
			models.UniqueConstraint(fields=["effective_from"], name="unique_global_rules_effective_date"),
		]
		verbose_name = "parámetro legal global"
		verbose_name_plural = "parámetros legales globales"

	def clean(self):
		errors = {}
		for field in ("ivss_employee_rate", "faov_employee_rate", "unemployment_employee_rate"):
			rate = getattr(self, field)
			if rate < 0 or rate > 1:
				errors[field] = "La tasa debe estar entre 0 y 1 (por ejemplo, 0.04 para 4%)."
		if self.minimum_monthly_salary_bs <= 0:
			errors["minimum_monthly_salary_bs"] = "El salario mínimo de referencia debe ser positivo."
		if self.ivss_cap_minimum_wages < 0:
			errors["ivss_cap_minimum_wages"] = "El tope IVSS no puede ser negativo."
		if self.unemployment_cap_minimum_wages < 0:
			errors["unemployment_cap_minimum_wages"] = "El tope de paro forzoso no puede ser negativo."
		if errors:
			raise ValidationError(errors)

	def save(self, *args, **kwargs):
		if self.pk:
			original = LegalRuleSet.objects.filter(pk=self.pk).first()
			if original and any(
				getattr(self, field.attname) != getattr(original, field.attname)
				for field in self._meta.concrete_fields if not field.primary_key
			):
				raise ValidationError("Las reglas globales versionadas son inmutables; crea una nueva versión.")
		super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		raise ValidationError("No se pueden borrar reglas legales versionadas.")

	def __str__(self):
		return f"{self.name} · {self.effective_from}"


class PayrollRun(models.Model):
	institution = models.ForeignKey(
		Institution, on_delete=models.PROTECT, related_name="payroll_runs",
		verbose_name="Institución",
	)
	institution_name_snapshot = models.CharField("Institución al procesar", max_length=160, blank=True)
	institution_tax_id_snapshot = models.CharField("RIF al procesar", max_length=24, blank=True)
	period_start = models.DateField("Inicio del período")
	period_end = models.DateField("Fin del período")
	policy = models.ForeignKey(InstitutionPolicy, on_delete=models.PROTECT, verbose_name="Política aplicada")
	legal_rules = models.ForeignKey(
		LegalRuleSet, on_delete=models.PROTECT, null=True, blank=True,
		verbose_name="Reglas legales aplicadas",
	)
	exchange_rate_snapshot = models.DecimalField(
		"Tasa BCV aplicada (Bs/USD)", max_digits=18, decimal_places=6,
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
		verbose_name="Creado por",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-period_end", "-created_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["institution", "period_start", "period_end"],
				name="unique_payroll_period_per_institution",
			),
		]
		verbose_name = "corrida de nómina"
		verbose_name_plural = "corridas de nómina"

	def clean(self):
		if self.period_end and self.period_start and self.period_end < self.period_start:
			raise ValidationError({"period_end": "El fin del período debe ser posterior al inicio."})
		if self.policy_id and self.institution_id and self.policy.institution_id != self.institution_id:
			raise ValidationError({"policy": "La política debe pertenecer al liceo seleccionado."})

	def __str__(self):
		return f"{self.institution} · {self.period_start} – {self.period_end}"


class PayrollResult(models.Model):
	run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="results")
	employee = models.ForeignKey(Employee, on_delete=models.PROTECT, verbose_name="Empleado")
	employee_name_snapshot = models.CharField("Nombre al procesar", max_length=220, blank=True)
	employee_id_snapshot = models.CharField("Cédula al procesar", max_length=24, blank=True)
	contract_type_snapshot = models.CharField(
		"Contrato al procesar", max_length=24, choices=Employee.ContractType.choices, blank=True,
	)
	calculation_snapshot = models.JSONField("Datos de cálculo congelados", default=dict)
	salary_base_monthly_bs = models.DecimalField("Salario base mensual (Bs)", max_digits=18, decimal_places=2)
	salary_base_daily_bs = models.DecimalField("Salario base diario (Bs)", max_digits=18, decimal_places=6)
	normal_monthly_bs = models.DecimalField("Salario normal mensual (Bs)", max_digits=18, decimal_places=2)
	normal_daily_bs = models.DecimalField("Salario normal diario (Bs)", max_digits=18, decimal_places=6)
	utility_allowance_daily_bs = models.DecimalField("Alícuota utilidades diaria (Bs)", max_digits=18, decimal_places=6)
	vacation_allowance_daily_bs = models.DecimalField("Alícuota vacacional diaria (Bs)", max_digits=18, decimal_places=6)
	integral_daily_bs = models.DecimalField("Salario integral diario (Bs)", max_digits=18, decimal_places=6)
	cestaticket_bs = models.DecimalField("Cestaticket (Bs)", max_digits=18, decimal_places=2)
	ivss_bs = models.DecimalField("Retención IVSS (Bs)", max_digits=18, decimal_places=2, default=0)
	faov_bs = models.DecimalField("Retención FAOV (Bs)", max_digits=18, decimal_places=2, default=0)
	unemployment_bs = models.DecimalField("Retención paro forzoso (Bs)", max_digits=18, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["employee__last_name", "employee__first_name"]
		constraints = [
			models.UniqueConstraint(fields=["run", "employee"], name="unique_employee_per_payroll_run"),
		]
		verbose_name = "resultado de nómina"
		verbose_name_plural = "resultados de nómina"

	@property
	def deductions_bs(self):
		return self.ivss_bs + self.faov_bs + self.unemployment_bs

	@property
	def net_bs(self):
		return self.normal_monthly_bs + self.cestaticket_bs - self.deductions_bs


class QuarterlyAccrual(models.Model):
	employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="benefit_accruals")
	quarter_end = models.DateField("Cierre del trimestre")
	integral_daily_bs = models.DecimalField("Salario integral diario (Bs)", max_digits=18, decimal_places=6)
	credited_days = models.PositiveSmallIntegerField("Días acreditados")
	amount_bs = models.DecimalField("Monto acreditado (Bs)", max_digits=18, decimal_places=2)
	payroll_result = models.OneToOneField(
		PayrollResult, on_delete=models.PROTECT, related_name="quarterly_accrual",
	)

	class Meta:
		ordering = ["quarter_end"]
		constraints = [
			models.UniqueConstraint(fields=["employee", "quarter_end"], name="unique_employee_quarter_accrual"),
		]
		verbose_name = "acumulación trimestral de prestaciones"
		verbose_name_plural = "acumulaciones trimestrales de prestaciones"

# Create your models here.
