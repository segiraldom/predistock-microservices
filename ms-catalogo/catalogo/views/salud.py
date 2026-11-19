"""Health check para Docker/Kubernetes (liveness/readiness)."""
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def salud(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return Response({"status": "error", "database": "no disponible"}, status=503)
    return Response({"status": "ok", "servicio": "ms-catalogo"})
