from django.http import JsonResponse
from django.urls import include, path

urlpatterns = [
    path("api/catalogo/", include("catalogo.urls")),
]


def no_encontrado(request, exception=None):
    return JsonResponse({"error": "NO_ENCONTRADO", "mensaje": "La ruta no existe en ms-catalogo"}, status=404)


def error_interno(request):
    return JsonResponse({"error": "ERROR_INTERNO", "mensaje": "Error inesperado en ms-catalogo"}, status=500)


handler404 = no_encontrado
handler500 = error_interno
