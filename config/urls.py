from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("workflows.urls")),
]

admin.site.site_header = "Gestione template e workbook"
admin.site.site_title = "Template e workbook"
admin.site.index_title = "Backoffice"
