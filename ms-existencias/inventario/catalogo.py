"""
Cliente HTTP del microservicio de catálogo (RNF02: nunca se accede a su base de datos).

- Las operaciones de escritura validan productos/proveedores y fallan con 422/503.
- El enriquecimiento de respuestas (nombre del producto) nunca hace fallar la consulta.
- Con CATALOGO_VALIDACION=false no se llama a catálogo (desarrollo sin ms-catalogo).
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

from .errores import ErrorNegocio

log = logging.getLogger(__name__)

TTL_CACHE = 60          # segundos que se reutiliza la respuesta de catálogo
TTL_CAIDO = 30          # segundos sin reintentar enriquecimiento si catálogo está caído
CLAVE_CAIDO = "catalogo:caido"

ETIQUETAS = {"productos": "producto", "proveedores": "proveedor"}


def _no_disponible(etiqueta):
    return ErrorNegocio(503, "CATALOGO_NO_DISPONIBLE",
                        f"No fue posible validar el {etiqueta}. Intente más tarde.")


def _obtener(recurso, recurso_id, exigir_activo=True):
    """Devuelve el recurso de catálogo como dict, o None si la validación está desactivada."""
    if not settings.CATALOGO_VALIDACION:
        return None

    etiqueta = ETIQUETAS[recurso]
    clave = f"catalogo:{recurso}:{recurso_id}"
    dato = cache.get(clave)

    if dato is None:
        url = f"{settings.CATALOGO_SERVICE_URL.rstrip('/')}/{recurso}/{recurso_id}"
        try:
            resp = requests.get(url, timeout=settings.HTTP_TIMEOUT)
        except requests.RequestException as exc:
            log.warning("Catálogo no disponible (%s): %s", url, exc)
            cache.set(CLAVE_CAIDO, True, TTL_CAIDO)
            raise _no_disponible(etiqueta)

        if resp.status_code == 404:
            raise ErrorNegocio(422, "REFERENCIA_INVALIDA", f"El {etiqueta} {recurso_id} no existe en catálogo")
        if resp.status_code != 200:
            log.warning("Catálogo respondió %s para %s", resp.status_code, url)
            raise _no_disponible(etiqueta)

        dato = resp.json()
        if isinstance(dato, dict) and isinstance(dato.get("data"), dict):
            dato = dato["data"]  # tolera respuestas envueltas en {"data": {...}}
        cache.set(clave, dato, TTL_CACHE)
        cache.delete(CLAVE_CAIDO)

    if exigir_activo and not dato.get("activo", True):
        raise ErrorNegocio(422, "REFERENCIA_INVALIDA", f"El {etiqueta} {recurso_id} está inactivo en catálogo")
    return dato


def obtener_producto(producto_id, exigir_activo=True):
    return _obtener("productos", producto_id, exigir_activo)


def obtener_proveedor(proveedor_id, exigir_activo=True):
    return _obtener("proveedores", proveedor_id, exigir_activo)


def nombres_productos(ids):
    """{producto_id: nombre} para enriquecer respuestas. Nunca lanza errores."""
    if not settings.CATALOGO_VALIDACION or cache.get(CLAVE_CAIDO):
        return {}
    nombres = {}
    for pid in ids:
        try:
            producto = obtener_producto(pid, exigir_activo=False)
        except ErrorNegocio:
            if cache.get(CLAVE_CAIDO):
                break  # no seguir esperando timeouts: RNF06
            continue
        if producto:
            nombres[pid] = producto.get("nombre")
    return nombres
