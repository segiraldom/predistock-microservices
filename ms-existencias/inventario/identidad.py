"""
Identidad del usuario propagada por el API Gateway.

El Gateway valida el JWT y reenvía X-Usuario-Id, X-Rol y X-Bodega-Id. Este servicio
confía en esas cabeceras, por eso su puerto no debe exponerse fuera de la red interna.
"""
from dataclasses import dataclass

from .errores import ErrorNegocio

ADMIN = "ADMIN"
OPERADOR_BODEGA = "OPERADOR_BODEGA"
ANALISTA = "ANALISTA"


def normalizar_rol(rol):
    """Misma normalización que JwtAuthenticate.php del Gateway."""
    limpio = (rol or "").strip().upper().replace(" ", "_").replace("-", "_")
    if limpio == "ADMINISTRADOR":
        return ADMIN
    if limpio == "OPERADOR_DE_BODEGA":
        return OPERADOR_BODEGA
    return limpio


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Identidad:
    usuario_id: int | None
    rol: str
    bodega_id: int | None

    @property
    def es_admin(self):
        return self.rol == ADMIN


def obtener_identidad(request):
    h = request.headers
    return Identidad(
        usuario_id=_entero(h.get("X-Usuario-Id")),
        rol=normalizar_rol(h.get("X-Rol")),
        bodega_id=_entero(h.get("X-Bodega-Id")),
    )


def exigir_rol(request, *roles):
    """Devuelve la identidad o lanza 403 si el rol no está entre los permitidos."""
    identidad = obtener_identidad(request)
    if identidad.rol not in roles:
        raise ErrorNegocio(403, "SIN_PERMISO", "El rol del usuario no tiene permiso para esta operación")
    return identidad
