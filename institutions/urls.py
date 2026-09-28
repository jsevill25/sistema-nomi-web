from django.urls import path

from . import views

urlpatterns = [
    path("", views.institution_list, name="institutions"),
    path("nueva/", views.institution_create, name="institution_create"),
    path("<int:pk>/editar/", views.institution_edit, name="institution_edit"),
    path("configuracion/nueva/", views.institution_policy_create, name="institution_policy_create"),
]