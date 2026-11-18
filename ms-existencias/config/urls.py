from django.urls import include, path

urlpatterns = [
    path("api/existencias/", include("inventario.urls")),
]
