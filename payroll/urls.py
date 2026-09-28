from django.urls import path

from . import views

urlpatterns = [
    path("", views.payroll_list, name="payrolls"),
    path("procesar/", views.payroll_create, name="payroll_create"),
    path("<int:pk>/", views.payroll_detail, name="payroll_detail"),
]