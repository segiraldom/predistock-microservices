from django.test import TestCase
from rest_framework.test import APIClient

from catalogo.models import Categoria, Producto, Proveedor, UnidadMedida

PREFIJO = "/api/catalogo"


class BaseAPITest(TestCase):
    """
    Clientes que simulan las cabeceras que agrega el API Gateway tras validar el JWT.

    `interno` no envía cabeceras: así consulta ms-existencias por la red interna.
    No se asumen ids fijos: en PostgreSQL las secuencias no se reinician entre tests.
    """

    def setUp(self):
        self.admin = self.cliente("ADMIN", usuario_id=1)
        self.operador = self.cliente("OPERADOR_BODEGA", usuario_id=2, bodega_id=1)
        self.analista = self.cliente("ANALISTA", usuario_id=3)
        self.interno = APIClient()

    @staticmethod
    def cliente(rol, usuario_id=1, bodega_id=None):
        c = APIClient()
        headers = {"HTTP_X_ROL": rol, "HTTP_X_USUARIO_ID": str(usuario_id)}
        if bodega_id is not None:
            headers["HTTP_X_BODEGA_ID"] = str(bodega_id)
        c.credentials(**headers)
        return c

    # ---------- fábricas de datos ----------

    def crear_categoria(self, nombre="Lácteos", padre=None, **kwargs):
        return Categoria.objects.create(nombre=nombre, categoria_padre=padre, **kwargs)

    def crear_unidad(self, codigo="UND", nombre="Unidad"):
        return UnidadMedida.objects.create(codigo=codigo, nombre=nombre)

    def crear_proveedor(self, nit="900123456-7", razon_social="Lácteos del Eje S.A.S.", **kwargs):
        return Proveedor.objects.create(nit=nit, razon_social=razon_social, **kwargs)

    def crear_producto(self, categoria=None, unidad=None, codigo="LAC-001", **kwargs):
        datos = {"nombre": "Leche entera 1L", "precio_venta": 4500, "costo": 3200}
        datos.update(kwargs)
        return Producto.objects.create(
            codigo=codigo,
            categoria=categoria or self.crear_categoria(nombre=f"Cat {codigo}"),
            unidad_medida=unidad or self.crear_unidad(codigo=f"U-{codigo}"[:10], nombre="Unidad"),
            **datos)

    def datos_producto(self, categoria=None, unidad=None, **kwargs):
        datos = {
            "codigo": "LAC-001", "nombre": "Leche entera 1L", "descripcion": "Leche entera en bolsa de 1 litro",
            "categoria_id": (categoria or Categoria.objects.get_or_create(nombre="Lácteos")[0]).id,
            "unidad_medida_id": (unidad or UnidadMedida.objects.get_or_create(codigo="UND", defaults={"nombre": "Unidad"})[0]).id,
            "precio_venta": 4500, "costo": 3200, "es_perecedero": True,
        }
        datos.update(kwargs)
        return datos
