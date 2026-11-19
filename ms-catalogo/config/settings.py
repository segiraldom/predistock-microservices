"""Configuración de ms-catalogo (PrediStock). Todo lo variable viene de entorno."""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-cambiar")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "catalogo",
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
        # ?host=/ruta/socket permite conectarse por socket Unix
        "HOST": parse_qs(u.query).get("host", [u.hostname])[0],
        "PORT": u.port or 5432,
    }


DATABASES = {"default": _database_from_url(os.getenv("DATABASE_URL"))}

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# La autenticación la hace el API Gateway (valida el JWT y envía X-Usuario-Id, X-Rol, X-Bodega-Id).
# Las lecturas no exigen identidad: ms-existencias consulta productos y proveedores por la red interna
# sin cabeceras. Las escrituras exigen rol ADMIN (ver catalogo/identidad.py).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "catalogo.errores.manejador_excepciones",
    "COERCE_DECIMAL_TO_STRING": False,  # el contrato define precios y costos como number
}

APPEND_SLASH = False  # el Gateway reenvía rutas sin barra final

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
