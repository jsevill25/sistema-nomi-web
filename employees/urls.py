from django.urls import path

from . import views

urlpatterns = [
	path("", views.employee_list, name="employees"),
	path("nuevo/", views.employee_create, name="employee_create"),
	path("<int:pk>/editar/", views.employee_edit, name="employee_edit"),
]