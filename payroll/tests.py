from decimal import Decimal

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from employees.models import Employee
from institutions.models import Institution, InstitutionMembership, InstitutionPolicy
from .models import LegalRuleSet
from .services import create_payroll_run, severance_for_result

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


class SalaryCalculationTests(SimpleTestCase):
    def setUp(self):
        self.terms = InstitutionTerms(
            bcv_rate=Decimal("100"),
            utility_days=90,
            vacation_days=15,
            vacation_days_per_year=1,
            cestaticket_usd=Decimal("40"),
            docente_scale_active=True,
            transport_is_salary=False,
        )

    def test_hourly_teacher_salary_and_non_salary_transport(self):
        result = calculate_salary(
            SalaryInput(
                contract_type="hourly_teacher",
                hours_per_month=Decimal("20"),
                hourly_rate_usd=Decimal("5"),
                regular_bonus_usd=Decimal("10"),
                transport_bonus_usd=Decimal("20"),
            ),
            self.terms,
        )
        self.assertEqual(result.salary_base_monthly_bs, Decimal("10000.00"))
        self.assertEqual(result.normal_monthly_bs, Decimal("11000.00"))
        self.assertEqual(result.cestaticket_bs, Decimal("4000.00"))
        self.assertEqual(
            result.integral_daily_bs,
            result.normal_daily_bs + result.utility_allowance_daily_bs + result.vacation_allowance_daily_bs,
        )

    def test_transport_and_scale_bonus_are_configurable(self):
        salary = SalaryInput(
            contract_type="full_time_teacher",
            monthly_salary_usd=Decimal("1000"),
            scale_bonus_usd=Decimal("100"),
            transport_bonus_usd=Decimal("50"),
        )
        result = calculate_salary(salary, self.terms)
        self.assertEqual(result.salary_base_monthly_bs, Decimal("110000.00"))
        self.assertEqual(result.normal_monthly_bs, Decimal("110000.00"))

        transport_salary_terms = InstitutionTerms(
            **{**self.terms.__dict__, "transport_is_salary": True}
        )
        with_transport = calculate_salary(salary, transport_salary_terms)
        self.assertEqual(with_transport.normal_monthly_bs, Decimal("115000.00"))

    def test_unknown_contract_and_negative_salary_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_salary(SalaryInput(contract_type="unknown"), self.terms)
        with self.assertRaises(ValueError):
            calculate_salary(
                SalaryInput(contract_type="administrative", monthly_salary_usd=Decimal("-1")),
                self.terms,
            )


class LegalCalculationTests(SimpleTestCase):
    def test_first_service_anniversary_accrues_additional_days(self):
        credit = calculate_quarterly_credit(
            integral_daily_bs=Decimal("100"),
            completed_years=1,
            anniversary_in_quarter=True,
            previous_additional_days=0,
        )
        self.assertEqual(credit.credited_days, 17)

    def test_withholdings_apply_configured_caps(self):
        result = calculate_withholdings(
            Decimal("10000"),
            RetentionRules(
                minimum_monthly_salary_bs=Decimal("1000"),
                ivss_employee_rate=Decimal("0.04"),
                ivss_cap_minimum_wages=Decimal("5"),
                faov_employee_rate=Decimal("0.01"),
                unemployment_employee_rate=Decimal("0.005"),
                unemployment_cap_minimum_wages=Decimal("10"),
            ),
        )
        self.assertEqual(result.ivss_bs, Decimal("200.00"))
        self.assertEqual(result.faov_bs, Decimal("100.00"))
        self.assertEqual(result.unemployment_bs, Decimal("50.00"))

    def test_weekly_withholding_scales_monthly_salary_and_caps(self):
        rules = RetentionRules(
            minimum_monthly_salary_bs=Decimal("1000"),
            ivss_employee_rate=Decimal("0.04"),
            ivss_cap_minimum_wages=Decimal("5"),
            faov_employee_rate=Decimal("0.01"),
            unemployment_employee_rate=Decimal("0.005"),
            unemployment_cap_minimum_wages=Decimal("10"),
        )
        monthly = calculate_withholdings(Decimal("10000"), rules)
        weekly = calculate_withholdings(Decimal("10000"), rules, period_weeks=Decimal("1"))
        self.assertEqual(weekly.ivss_bs, Decimal("46.15"))
        self.assertEqual(weekly.faov_bs, Decimal("23.08"))
        self.assertEqual(weekly.unemployment_bs, Decimal("11.54"))
        self.assertLess(weekly.ivss_bs, monthly.ivss_bs)

    def test_anniversary_credit_respects_additional_days_cap(self):
        credit = calculate_quarterly_credit(
            integral_daily_bs=Decimal("100"),
            completed_years=5,
            anniversary_in_quarter=True,
            previous_additional_days=30,
        )
        self.assertEqual(credit.credited_days, 15)
        self.assertEqual(credit.amount_bs, Decimal("1500.00"))

    def test_compare_severance_pays_greater_regime(self):
        result = compare_severance(
            prior_accruals=[AccrualInput(15, Decimal("1500"))],
            current_credit=AccrualInput(15, Decimal("1500")),
            years_of_service=Decimal("1"),
            final_integral_daily_bs=Decimal("200"),
        )
        self.assertEqual(result.quarterly_guarantee_bs, Decimal("3000.00"))
        self.assertEqual(result.retroactivity_bs, Decimal("6000.00"))
        self.assertEqual(result.winning_regime, "retroactividad")
        self.assertEqual(result.payable_bs, Decimal("6000.00"))


class InstitutionIsolationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="liceo-admin", password="test-password")
        self.own_institution = Institution.objects.create(name="Liceo Norte")
        self.other_institution = Institution.objects.create(name="Liceo Sur")
        InstitutionMembership.objects.create(
            institution=self.own_institution,
            user=self.user,
            role=InstitutionMembership.Role.ADMIN,
        )
        Employee.objects.create(
            institution=self.own_institution,
            first_name="Ana",
            last_name="Propia",
            national_id="V-100",
            job_title="Docente",
            contract_type=Employee.ContractType.ADMINISTRATIVE,
            hire_date=date(2020, 1, 1),
            monthly_salary_usd=Decimal("500"),
        )
        Employee.objects.create(
            institution=self.other_institution,
            first_name="Luis",
            last_name="Ajeno",
            national_id="V-200",
            job_title="Docente",
            contract_type=Employee.ContractType.ADMINISTRATIVE,
            hire_date=date(2020, 1, 1),
            monthly_salary_usd=Decimal("500"),
        )
        self.client.force_login(self.user)

    def test_employee_directory_only_shows_assigned_institution(self):
        response = self.client.get(reverse("employees"))
        self.assertContains(response, "Ana Propia")
        self.assertNotContains(response, "Luis Ajeno")

    def test_employee_form_cannot_select_another_institution(self):
        response = self.client.get(reverse("employee_create"))
        self.assertContains(response, "Liceo Norte")
        self.assertNotContains(response, "Liceo Sur")

    def test_dashboard_and_institution_directory_render_for_member(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        response = self.client.get(reverse("institutions"))
        self.assertContains(response, "Liceo Norte")
        self.assertNotContains(response, "Liceo Sur")

    def test_viewer_cannot_operate_employee_form(self):
        membership = self.user.institution_memberships.get(institution=self.own_institution)
        membership.role = InstitutionMembership.Role.VIEWER
        membership.save(update_fields=["role"])
        response = self.client.get(reverse("employee_create"))
        self.assertNotContains(response, "Liceo Norte")


class PayrollRunIntegrationTests(TestCase):
    def test_quarter_end_run_freezes_policy_and_records_benefit_credit(self):
        user = get_user_model().objects.create_user(username="payroll-operator")
        institution = Institution.objects.create(name="Colegio Central")
        policy = InstitutionPolicy.objects.create(
            institution=institution,
            version=1,
            effective_from=date(2026, 1, 1),
            bcv_rate=Decimal("100"),
            utility_days=90,
            vacation_days=15,
            cestaticket_usd=Decimal("40"),
            docente_scale_active=True,
            transport_is_salary=False,
        )
        LegalRuleSet.objects.create(
            name="Reglas de prueba",
            effective_from=date(2026, 1, 1),
            minimum_monthly_salary_bs=Decimal("1000"),
            ivss_employee_rate=Decimal("0.04"),
            ivss_cap_minimum_wages=Decimal("5"),
            faov_employee_rate=Decimal("0.01"),
            unemployment_employee_rate=Decimal("0.005"),
            unemployment_cap_minimum_wages=Decimal("10"),
        )
        Employee.objects.create(
            institution=institution,
            first_name="Marta",
            last_name="Docente",
            national_id="V-500",
            job_title="Profesora",
            contract_type=Employee.ContractType.FULL_TIME_TEACHER,
            hire_date=date(2020, 1, 1),
            monthly_salary_usd=Decimal("500"),
            scale_bonus_usd=Decimal("50"),
        )

        run = create_payroll_run(
            institution, date(2026, 3, 1), date(2026, 3, 31), user,
        )
        InstitutionMembership.objects.create(
            institution=institution,
            user=user,
            role=InstitutionMembership.Role.OPERATOR,
        )
        result = run.results.get()
        accrual = result.quarterly_accrual
        severance = severance_for_result(result)

        self.assertEqual(run.policy, policy)
        self.assertEqual(run.exchange_rate_snapshot, Decimal("100"))
        self.assertEqual(result.salary_base_monthly_bs, Decimal("55000.00"))
        self.assertEqual(result.salary_base_daily_bs, Decimal("1833.333333"))
        self.assertEqual(result.employee_name_snapshot, "Marta Docente")
        self.assertEqual(result.calculation_snapshot["institution_policy"]["utility_days"], 90)
        self.assertEqual(accrual.credited_days, 17)
        self.assertGreater(accrual.amount_bs, Decimal("0"))
        self.assertEqual(severance.quarterly_guarantee_bs, accrual.amount_bs)
        self.client.force_login(user)
        response = self.client.get(reverse("payroll_detail", args=[run.pk]))
        self.assertContains(response, "Marta Docente")
        self.assertContains(response, "Bs. 100")
        with self.assertRaises(ValidationError):
            create_payroll_run(institution, date(2026, 3, 1), date(2026, 3, 31), user)
        with self.assertRaisesMessage(ValidationError, "mes calendario completo"):
            create_payroll_run(institution, date(2026, 4, 1), date(2026, 4, 15), user)
