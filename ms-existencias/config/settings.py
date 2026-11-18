"""Configuración de ms-existencias (PrediStock). Todo lo variable viene de entorno."""
import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-cambiar")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "inventario",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"


def _database_from_url(url):
    """postgresql://user:pass@host:port/name -> dict de Django. Sin URL: SQLite local (solo desarrollo/tests)."""
    if not url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    if url.startswith("sqlite:///"):
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": url[len("sqlite:///"):]}
    u = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password,
        "HOST": u.hostname,
        "PORT": u.port or 5432,
    }


DATABASES = {"default": _database_from_url(os.getenv("DATABASE_URL"))}

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# La autenticación la hace el API Gateway (valida el JWT y envía X-Usuario-Id, X-Rol, X-Bodega-Id).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "inventario.errores.manejador_excepciones",
    "COERCE_DECIMAL_TO_STRING": False,  # el contrato define las cantidades como number
}

APPEND_SLASH = False  # el Gateway reenvía rutas sin barra final

# Integración con otros microservicios (RNF02: nunca por base de datos)
CATALOGO_SERVICE_URL = os.getenv("CATALOGO_SERVICE_URL", "http://ms-catalogo:8001/api/catalogo")
CATALOGO_VALIDACION = os.getenv("CATALOGO_VALIDACION", "true").lower() == "true"
NOTIFICACIONES_SERVICE_URL = os.getenv("NOTIFICACIONES_SERVICE_URL", "http://ms-notificaciones:5001/api/notifications")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "3"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
