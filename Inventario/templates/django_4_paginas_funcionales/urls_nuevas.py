from django.urls import path
from . import views

urlpatterns = [
    # Mantén tus rutas existentes y agrega estas:
    path("producto/<int:id>/", views.producto, name="producto"),
    path("nosotros/", views.nosotros, name="nosotros"),
    path("contacto/", views.contacto, name="contacto"),
    path("cotizador/", views.cotizador, name="cotizador"),
]
