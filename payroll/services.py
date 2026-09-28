"""Orchestration layer: database access around the pure calculations module."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from employees.models import Employee
from institutions.models import Institution, InstitutionPolicy

from .calculations import (
    AccrualInput,
    InstitutionTerms,
    RetentionRules,
    SalaryInput,
    calculate_quarterly_credit,
    calculate_salary,
    calculate_withholdings,
    compare_severance,
)
from .models import LegalRuleSet, PayrollResult, PayrollRun, QuarterlyAccrual


def completed_years(hire_date: date, on_date: date) -> int:
    years = on_date.year - hire_date.year
    try:
        anniversary = hire_date.replace(year=on_date.year)
    except ValueError:
        anniversary = date(on_date.year, 2, 28)
    return max(years - (on_date < anniversary), 0)


def _quarter_dates(period_end: date):
    quarter_month = ((period_end.month - 1) // 3 + 1) * 3
    quarter_end = date(period_end.year, quarter_month, monthrange(period_end.year, quarter_month)[1])
    previous_month = quarter_month - 3
    if previous_month == 0:
        previous_end = date(period_end.year - 1, 12, 31)
    else:
        previous_end = date(period_end.year, previous_month, monthrange(period_end.year, previous_month)[1])
    return quarter_end, previous_end


@transaction.atomic
def create_payroll_run(institution: Institution, period_start: date, period_end: date, user):
    if period_end < period_start:
        raise ValidationError("El fin del período debe ser posterior al inicio.")
    if (
        period_start.day != 1
        or period_start.year != period_end.year
        or period_start.month != period_end.month
        or period_end.day != monthrange(period_end.year, period_end.month)[1]
    ):
        raise ValidationError("La corrida mensual debe abarcar un mes calendario completo.")
    if PayrollRun.objects.filter(
        institution=institution, period_start=period_start, period_end=period_end,
    ).exists():
        raise ValidationError("Ya existe una corrida para este liceo y período.")

    policy = InstitutionPolicy.objects.filter(
        institution=institution, effective_from__lte=period_end,
    ).first()
    if policy is None:
        raise ValidationError("Crea una configuración del liceo vigente para el fin del período.")
    legal_rules = LegalRuleSet.objects.filter(effective_from__lte=period_end).first()
    if legal_rules is None:
        raise ValidationError("Configura primero los parámetros legales globales en el panel admin.")
    employees = list(Employee.objects.filter(
        institution=institution,
        is_active=True,
        hire_date__lte=period_end,
    ))
    if not employees:
        raise ValidationError("El liceo no tiene empleados activos para procesar.")

    run = PayrollRun.objects.create(
        institution=institution,
        institution_name_snapshot=institution.name,
        institution_tax_id_snapshot=institution.tax_id,
        period_start=period_start,
        period_end=period_end,
        policy=policy,
        legal_rules=legal_rules,
        exchange_rate_snapshot=policy.bcv_rate,
        created_by=user,
    )
    terms = InstitutionTerms(
        bcv_rate=policy.bcv_rate,
        utility_days=policy.utility_days,
        vacation_days=policy.vacation_days,
        vacation_days_per_year=policy.vacation_days_per_year,
        cestaticket_usd=policy.cestaticket_usd,
        docente_scale_active=policy.docente_scale_active,
        transport_is_salary=policy.transport_is_salary,
    )
    retention_rules = RetentionRules(
        minimum_monthly_salary_bs=legal_rules.minimum_monthly_salary_bs,
        ivss_employee_rate=legal_rules.ivss_employee_rate,
        ivss_cap_minimum_wages=legal_rules.ivss_cap_minimum_wages,
        faov_employee_rate=legal_rules.faov_employee_rate,
        unemployment_employee_rate=legal_rules.unemployment_employee_rate,
        unemployment_cap_minimum_wages=legal_rules.unemployment_cap_minimum_wages,
    )

    quarter_end, previous_quarter_end = _quarter_dates(period_end)
    is_quarter_close = period_end == quarter_end
    for employee in employees:
        years = completed_years(employee.hire_date, period_end)
        salary = calculate_salary(
            SalaryInput(
                contract_type=employee.contract_type,
                monthly_salary_usd=employee.monthly_salary_usd,
                hours_per_month=employee.hours_per_month,
                hourly_rate_usd=employee.hourly_rate_usd,
                regular_bonus_usd=employee.regular_bonus_usd,
                transport_bonus_usd=employee.transport_bonus_usd,
                scale_bonus_usd=employee.scale_bonus_usd,
                completed_years=years,
            ),
            terms,
        )
        deductions = calculate_withholdings(salary.normal_monthly_bs, retention_rules)
        result = PayrollResult.objects.create(
            run=run,
            employee=employee,
            employee_name_snapshot=employee.full_name,
            employee_id_snapshot=employee.national_id,
            contract_type_snapshot=employee.contract_type,
            calculation_snapshot={
                "employee": {
                    "hire_date": employee.hire_date.isoformat(),
                    "monthly_salary_usd": str(employee.monthly_salary_usd),
                    "hours_per_month": str(employee.hours_per_month),
                    "hourly_rate_usd": str(employee.hourly_rate_usd),
                    "regular_bonus_usd": str(employee.regular_bonus_usd),
                    "transport_bonus_usd": str(employee.transport_bonus_usd),
                    "scale_bonus_usd": str(employee.scale_bonus_usd),
                    "completed_years": years,
                },
                "institution_policy": {
                    "version": policy.version,
                    "effective_from": policy.effective_from.isoformat(),
                    "bcv_rate": str(policy.bcv_rate),
                    "utility_days": policy.utility_days,
                    "vacation_days": policy.vacation_days,
                    "vacation_days_per_year": policy.vacation_days_per_year,
                    "cestaticket_usd": str(policy.cestaticket_usd),
                    "docente_scale_active": policy.docente_scale_active,
                    "transport_is_salary": policy.transport_is_salary,
                },
                "legal_rules": {
                    "id": legal_rules.pk,
                    "effective_from": legal_rules.effective_from.isoformat(),
                    "minimum_monthly_salary_bs": str(legal_rules.minimum_monthly_salary_bs),
                    "ivss_employee_rate": str(legal_rules.ivss_employee_rate),
                    "ivss_cap_minimum_wages": str(legal_rules.ivss_cap_minimum_wages),
                    "faov_employee_rate": str(legal_rules.faov_employee_rate),
                    "unemployment_employee_rate": str(legal_rules.unemployment_employee_rate),
                    "unemployment_cap_minimum_wages": str(legal_rules.unemployment_cap_minimum_wages),
                },
            },
            salary_base_monthly_bs=salary.salary_base_monthly_bs,
            salary_base_daily_bs=salary.salary_base_daily_bs,
            normal_monthly_bs=salary.normal_monthly_bs,
            normal_daily_bs=salary.normal_daily_bs,
            utility_allowance_daily_bs=salary.utility_allowance_daily_bs,
            vacation_allowance_daily_bs=salary.vacation_allowance_daily_bs,
            integral_daily_bs=salary.integral_daily_bs,
            cestaticket_bs=salary.cestaticket_bs,
            ivss_bs=deductions.ivss_bs,
            faov_bs=deductions.faov_bs,
            unemployment_bs=deductions.unemployment_bs,
        )
        if is_quarter_close and employee.hire_date <= period_end:
            previous_years = completed_years(employee.hire_date, previous_quarter_end)
            prior_records = list(employee.benefit_accruals.filter(quarter_end__lt=period_end))
            prior_extra_days = sum(max(record.credited_days - 15, 0) for record in prior_records)
            credit = calculate_quarterly_credit(
                integral_daily_bs=salary.integral_daily_bs,
                completed_years=years,
                anniversary_in_quarter=years > previous_years,
                previous_additional_days=prior_extra_days,
                additional_days_per_year=legal_rules.additional_benefit_days_per_year,
                additional_days_cap=legal_rules.additional_benefit_days_cap,
            )
            QuarterlyAccrual.objects.create(
                employee=employee,
                quarter_end=period_end,
                integral_daily_bs=salary.integral_daily_bs,
                credited_days=credit.credited_days,
                amount_bs=credit.amount_bs,
                payroll_result=result,
            )
    return run


def severance_for_result(result: PayrollResult):
    employee = result.employee
    accruals = list(employee.benefit_accruals.filter(
        quarter_end__lte=result.run.period_end,
    ).exclude(payroll_result=result).order_by("quarter_end"))
    current = getattr(result, "quarterly_accrual", None)
    current_amount = current.amount_bs if current else Decimal("0")
    years = Decimal((result.run.period_end - employee.hire_date).days) / Decimal("365")
    return compare_severance(
        prior_accruals=[
            AccrualInput(item.credited_days, item.amount_bs) for item in accruals
        ],
        current_credit=AccrualInput(current.credited_days, current_amount) if current else AccrualInput(0, Decimal("0")),
        years_of_service=years,
        final_integral_daily_bs=result.integral_daily_bs,
    )