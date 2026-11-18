from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from inventario.models import Bodega

PREFIJO = "/api/existencias"


@override_settings(CATALOGO_VALIDACION=False, NOTIFICACIONES_ASINCRONO=False,
                   NOTIFICACIONES_SERVICE_URL="http://notif/api/notifications")
class BaseAPITest(TestCase):
    """Cliente que simula las cabeceras que agrega el API Gateway tras validar el JWT."""

    def setUp(self):
        cache.clear()
        self.admin = self.cliente("ADMIN", usuario_id=1)
        self.operador = self.cliente("OPERADOR_BODEGA", usuario_id=2, bodega_id=1)

    @staticmethod
    def cliente(rol, usuario_id=1, bodega_id=None):
        c = APIClient()
        headers = {"HTTP_X_ROL": rol, "HTTP_X_USUARIO_ID": str(usuario_id)}
        if bodega_id is not None:
            headers["HTTP_X_BODEGA_ID"] = str(bodega_id)
        c.credentials(**headers)
        return c

    @staticmethod
    def crear_bodega(codigo="BOD-MZL", **kwargs):
        datos = {"nombre": "Bodega Manizales", "region": "Centro", "ciudad": "Manizales"}
        datos.update(kwargs)
        return Bodega.objects.create(codigo=codigo, **datos)
