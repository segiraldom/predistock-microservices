from django.http import JsonResponse
from django.urls import include, path

urlpatterns = [
    path("api/existencias/", include("inventario.urls")),
]


def no_encontrado(request, exception=None):
    return JsonResponse({"error": "NO_ENCONTRADO", "mensaje": "La ruta no existe en ms-existencias"}, status=404)


def error_interno(request):
    return JsonResponse({"error": "ERROR_INTERNO", "mensaje": "Error inesperado en ms-existencias"}, status=500)


handler404 = no_encontrado
handler500 = error_interno
