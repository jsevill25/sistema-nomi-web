from django.contrib import admin

from .models import Institution, InstitutionMembership, InstitutionPolicy


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
	list_display = ("name", "tax_id", "is_active")
	list_filter = ("is_active",)
	search_fields = ("name", "legal_name", "tax_id")


@admin.register(InstitutionPolicy)
class InstitutionPolicyAdmin(admin.ModelAdmin):
	list_display = (
		"institution", "version", "effective_from", "bcv_rate",
		"utility_days", "vacation_days", "cestaticket_usd",
	)
	list_filter = ("institution", "effective_from", "docente_scale_active", "transport_is_salary")
	search_fields = ("institution__name",)
	ordering = ("-effective_from",)

	def get_readonly_fields(self, request, obj=None):
		return tuple(field.name for field in self.model._meta.fields) if obj else ()

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(InstitutionMembership)
class InstitutionMembershipAdmin(admin.ModelAdmin):
	list_display = ("user", "institution", "role")
	list_filter = ("institution", "role")
	search_fields = ("user__username", "user__email", "institution__name")

	def has_module_permission(self, request):
		return request.user.is_superuser

	def has_view_permission(self, request, obj=None):
		return request.user.is_superuser

	def has_add_permission(self, request):
		return request.user.is_superuser

	def has_change_permission(self, request, obj=None):
		return request.user.is_superuser

	def has_delete_permission(self, request, obj=None):
		return request.user.is_superuser

# Register your models here.
