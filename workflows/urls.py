from django.urls import path

from . import views

urlpatterns = [
    path("l/<uuid:token>/", views.public_form, name="public-form"),
]
