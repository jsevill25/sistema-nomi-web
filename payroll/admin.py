from django.contrib import admin

from .models import LegalRuleSet, PayrollResult, PayrollRun, QuarterlyAccrual


@admin.register(LegalRuleSet)
class LegalRuleSetAdmin(admin.ModelAdmin):
	list_display = ("name", "effective_from", "minimum_monthly_salary_bs")
	ordering = ("-effective_from",)

	def get_readonly_fields(self, request, obj=None):
		return tuple(field.name for field in self.model._meta.fields) if obj else ()

	def has_delete_permission(self, request, obj=None):
		return False


class PayrollResultInline(admin.TabularInline):
	model = PayrollResult
	extra = 0
	can_delete = False
	readonly_fields = tuple(field.name for field in PayrollResult._meta.fields)
	show_change_link = True

	def has_add_permission(self, request, obj=None):
		return False


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
	list_display = ("institution", "period_start", "period_end", "exchange_rate_snapshot", "created_at")
	list_filter = ("institution", "period_end")
	readonly_fields = ("exchange_rate_snapshot", "created_by", "created_at")
	inlines = (PayrollResultInline,)

	def get_readonly_fields(self, request, obj=None):
		if obj:
			return tuple(field.name for field in self.model._meta.fields)
		return self.readonly_fields

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(PayrollResult)
class PayrollResultAdmin(admin.ModelAdmin):
	list_display = ("employee", "run", "normal_monthly_bs", "cestaticket_bs", "ivss_bs", "faov_bs")
	list_filter = ("run__institution", "run__period_end")
	search_fields = ("employee__first_name", "employee__last_name", "employee__national_id")

	def get_readonly_fields(self, request, obj=None):
		return tuple(field.name for field in self.model._meta.fields) if obj else ()

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(QuarterlyAccrual)
class QuarterlyAccrualAdmin(admin.ModelAdmin):
	list_display = ("employee", "quarter_end", "credited_days", "amount_bs")
	list_filter = ("quarter_end", "employee__institution")
	search_fields = ("employee__first_name", "employee__last_name", "employee__national_id")

	def get_readonly_fields(self, request, obj=None):
		return tuple(field.name for field in self.model._meta.fields) if obj else ()

	def has_delete_permission(self, request, obj=None):
		return False

# Register your models here.
