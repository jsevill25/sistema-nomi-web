from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
	list_display = ("national_id", "full_name", "institution", "contract_type", "job_title", "is_active")
	list_filter = ("institution", "contract_type", "is_active")
	search_fields = ("national_id", "first_name", "last_name", "job_title")
	list_select_related = ("institution",)

# Register your models here.
