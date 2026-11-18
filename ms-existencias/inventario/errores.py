"""Formato de error uniforme del contrato: {"error": CODIGO, "mensaje": texto}."""
from rest_framework.response import Response
from rest_framework.views import exception_handler

CODIGOS_HTTP = {
    400: "DATOS_INVALIDOS",
    401: "NO_AUTORIZADO",
    403: "SIN_PERMISO",
    404: "NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    415: "TIPO_NO_SOPORTADO",
}


class ErrorNegocio(Exception):
    """Error de regla de negocio con código HTTP y código de error propios."""

    def __init__(self, status, codigo, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje


def manejador_excepciones(exc, context):
    if isinstance(exc, ErrorNegocio):
        return Response({"error": exc.codigo, "mensaje": exc.mensaje}, status=exc.status)

    resp = exception_handler(exc, context)
    if resp is None:
        return None  # error no controlado: lo atiende handler500 (config/urls.py)

    data = resp.data
    if isinstance(data, dict) and set(data) == {"detail"}:
        mensaje = str(data["detail"])
    else:
        mensaje = data  # errores de validación campo por campo
    resp.data = {"error": CODIGOS_HTTP.get(resp.status_code, "ERROR"), "mensaje": mensaje}
    return resp
