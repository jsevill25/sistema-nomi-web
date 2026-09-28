"""Pure payroll calculations. Legal values are injected, never embedded here."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0")
CENT = Decimal("0.01")
MICRO = Decimal("0.000001")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_daily(value: Decimal) -> Decimal:
    return value.quantize(MICRO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SalaryInput:
    contract_type: str
    monthly_salary_usd: Decimal = ZERO
    hours_per_month: Decimal = ZERO
    hourly_rate_usd: Decimal = ZERO
    regular_bonus_usd: Decimal = ZERO
    transport_bonus_usd: Decimal = ZERO
    scale_bonus_usd: Decimal = ZERO
    completed_years: int = 0


@dataclass(frozen=True)
class InstitutionTerms:
    bcv_rate: Decimal
    utility_days: int
    vacation_days: int
    vacation_days_per_year: int
    cestaticket_usd: Decimal
    docente_scale_active: bool
    transport_is_salary: bool


@dataclass(frozen=True)
class SalaryBreakdown:
    salary_base_monthly_bs: Decimal
    salary_base_daily_bs: Decimal
    normal_monthly_bs: Decimal
    normal_daily_bs: Decimal
    utility_allowance_daily_bs: Decimal
    vacation_allowance_daily_bs: Decimal
    integral_daily_bs: Decimal
    cestaticket_bs: Decimal


def calculate_salary(inputs: SalaryInput, terms: InstitutionTerms) -> SalaryBreakdown:
    """Calculate one month's normal and integral salary in payment currency (VES)."""
    if terms.bcv_rate <= ZERO:
        raise ValueError("La tasa BCV debe ser mayor que cero.")
    if terms.utility_days < 30 or terms.vacation_days < 15:
        raise ValueError("Los días configurados están por debajo del mínimo indicado.")
    if min(
        inputs.monthly_salary_usd, inputs.hours_per_month, inputs.hourly_rate_usd,
        inputs.regular_bonus_usd, inputs.transport_bonus_usd, inputs.scale_bonus_usd,
    ) < ZERO or inputs.completed_years < 0:
        raise ValueError("Los salarios, bonos, horas y años de servicio no pueden ser negativos.")

    if inputs.contract_type == "hourly_teacher":
        if inputs.hours_per_month <= ZERO or inputs.hourly_rate_usd <= ZERO:
            raise ValueError("El profesor por hora requiere horas y valor hora positivos.")
        base_usd = inputs.hours_per_month * inputs.hourly_rate_usd
    elif inputs.contract_type in {"administrative", "worker", "full_time_teacher"}:
        if inputs.monthly_salary_usd <= ZERO:
            raise ValueError("El contrato mensual requiere un sueldo positivo.")
        base_usd = inputs.monthly_salary_usd
        if inputs.contract_type == "full_time_teacher" and terms.docente_scale_active:
            base_usd += inputs.scale_bonus_usd
    else:
        raise ValueError("Tipo de contrato no soportado.")

    normal_usd = base_usd + inputs.regular_bonus_usd
    if terms.transport_is_salary:
        normal_usd += inputs.transport_bonus_usd

    base_monthly_bs = base_usd * terms.bcv_rate
    normal_monthly_bs = normal_usd * terms.bcv_rate
    normal_daily_bs = normal_monthly_bs / Decimal("30")
    vacation_days = terms.vacation_days + (
        max(inputs.completed_years, 0) * terms.vacation_days_per_year
    )
    utility_daily = Decimal(terms.utility_days) / Decimal("360") * normal_daily_bs
    vacation_daily = Decimal(vacation_days) / Decimal("360") * normal_daily_bs
    rounded_normal_daily = quantize_daily(normal_daily_bs)
    rounded_utility_daily = quantize_daily(utility_daily)
    rounded_vacation_daily = quantize_daily(vacation_daily)
    integral_daily = rounded_normal_daily + rounded_utility_daily + rounded_vacation_daily

    return SalaryBreakdown(
        salary_base_monthly_bs=quantize_money(base_monthly_bs),
        salary_base_daily_bs=quantize_daily(base_monthly_bs / Decimal("30")),
        normal_monthly_bs=quantize_money(normal_monthly_bs),
        normal_daily_bs=rounded_normal_daily,
        utility_allowance_daily_bs=rounded_utility_daily,
        vacation_allowance_daily_bs=rounded_vacation_daily,
        integral_daily_bs=quantize_daily(integral_daily),
        cestaticket_bs=quantize_money(terms.cestaticket_usd * terms.bcv_rate),
    )


@dataclass(frozen=True)
class RetentionRules:
    minimum_monthly_salary_bs: Decimal
    ivss_employee_rate: Decimal
    ivss_cap_minimum_wages: Decimal
    faov_employee_rate: Decimal
    unemployment_employee_rate: Decimal
    unemployment_cap_minimum_wages: Decimal


@dataclass(frozen=True)
class Withholdings:
    ivss_bs: Decimal
    faov_bs: Decimal
    unemployment_bs: Decimal


def calculate_withholdings(
    normal_monthly_bs: Decimal,
    rules: RetentionRules,
    period_weeks: Decimal = Decimal("52") / Decimal("12"),
) -> Withholdings:
    """Apply configured caps for the requested period; legal rates remain injected."""
    if normal_monthly_bs < ZERO or rules.minimum_monthly_salary_bs <= ZERO or period_weeks <= ZERO:
        raise ValueError("El salario y el salario mínimo de referencia deben ser válidos.")
    rates = (
        rules.ivss_employee_rate,
        rules.faov_employee_rate,
        rules.unemployment_employee_rate,
    )
    caps = (rules.ivss_cap_minimum_wages, rules.unemployment_cap_minimum_wages)
    if any(rate < ZERO or rate > Decimal("1") for rate in rates) or any(cap < ZERO for cap in caps):
        raise ValueError("Las tasas deben estar entre 0 y 1 y los topes no pueden ser negativos.")
    period_factor = period_weeks / (Decimal("52") / Decimal("12"))
    normal_period_bs = normal_monthly_bs * period_factor
    minimum_period_bs = rules.minimum_monthly_salary_bs * period_factor
    ivss_base = min(
        normal_period_bs,
        minimum_period_bs * rules.ivss_cap_minimum_wages,
    )
    unemployment_base = min(
        normal_period_bs,
        minimum_period_bs * rules.unemployment_cap_minimum_wages,
    )
    return Withholdings(
        ivss_bs=quantize_money(ivss_base * rules.ivss_employee_rate),
        faov_bs=quantize_money(normal_period_bs * rules.faov_employee_rate),
        unemployment_bs=quantize_money(
            unemployment_base * rules.unemployment_employee_rate
        ),
    )


@dataclass(frozen=True)
class AccrualInput:
    credited_days: int
    amount_bs: Decimal


@dataclass(frozen=True)
class QuarterlyCredit:
    credited_days: int
    amount_bs: Decimal


def calculate_quarterly_credit(
    integral_daily_bs: Decimal,
    completed_years: int,
    anniversary_in_quarter: bool,
    previous_additional_days: int,
    additional_days_per_year: int = 2,
    additional_days_cap: int = 30,
) -> QuarterlyCredit:
    """Accrue 15 quarterly days and add the anniversary credit when it applies."""
    if integral_daily_bs < ZERO or min(
        completed_years, previous_additional_days, additional_days_per_year, additional_days_cap,
    ) < 0:
        raise ValueError("Los valores de prestaciones no pueden ser negativos.")
    extra_days = 0
    if anniversary_in_quarter and completed_years >= 1:
        extra_days = min(
            additional_days_per_year,
            max(additional_days_cap - previous_additional_days, 0),
        )
    days = 15 + extra_days
    return QuarterlyCredit(
        credited_days=days,
        amount_bs=quantize_money(Decimal(days) * integral_daily_bs),
    )


@dataclass(frozen=True)
class SeveranceComparison:
    quarterly_guarantee_bs: Decimal
    retroactivity_bs: Decimal
    payable_bs: Decimal
    winning_regime: str

    @property
    def winning_regime_label(self) -> str:
        labels = {
            "garantia_trimestral": "Garantía trimestral",
            "retroactividad": "Retroactividad",
        }
        return labels[self.winning_regime]


def compare_severance(
    prior_accruals: list[AccrualInput],
    current_credit: AccrualInput,
    years_of_service: Decimal,
    final_integral_daily_bs: Decimal,
) -> SeveranceComparison:
    """Compare accumulated quarterly guarantees with the Art. 142 retroactivity."""
    if years_of_service < ZERO or final_integral_daily_bs < ZERO:
        raise ValueError("Los años de servicio y el último salario deben ser válidos.")
    guarantee = sum((item.amount_bs for item in prior_accruals), ZERO)
    guarantee += current_credit.amount_bs
    retroactivity = (
        Decimal("30") * years_of_service * final_integral_daily_bs
    )
    guarantee = quantize_money(guarantee)
    retroactivity = quantize_money(retroactivity)
    if guarantee >= retroactivity:
        return SeveranceComparison(guarantee, retroactivity, guarantee, "garantia_trimestral")
    return SeveranceComparison(guarantee, retroactivity, retroactivity, "retroactividad")