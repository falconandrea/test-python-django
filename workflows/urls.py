from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="workflows/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template-edit"),
    path("workbooks/new/", views.workbook_create, name="workbook-create"),
    path("workbooks/<int:pk>/", views.public_form, name="workbook-fill"),
    path("workbooks/<int:pk>/edit/", views.workbook_edit, name="workbook-edit"),
    path("workbooks/<int:pk>/responses/", views.workbook_responses, name="workbook-responses"),
]
