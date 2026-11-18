"""Formato de error uniforme del contrato: {"error": CODIGO, "mensaje": texto}."""
from rest_framework.response import Response
from rest_framework.views import exception_handler


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
    if resp is not None:
        resp.data = {"error": "DATOS_INVALIDOS" if resp.status_code == 400 else "ERROR", "mensaje": resp.data}
    return resp
