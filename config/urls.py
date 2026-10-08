from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("workflows.urls")),
    re_path(r"^$", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
]

admin.site.site_header = "Gestione template compilabili"
admin.site.site_title = "Template compilabili"
admin.site.index_title = "Backoffice"
