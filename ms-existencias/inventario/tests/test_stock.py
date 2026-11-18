from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.test import override_settings

from inventario.models import Existencia

from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/stock"


class StockTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.bodega = self.crear_bodega()

    def registrar(self, producto_id=12, **extra):
        datos = {"producto_id": producto_id, "bodega_id": self.bodega.id, "stock_minimo": 100, "stock_maximo": 500}
        datos.update(extra)
        return self.admin.post(URL, datos, format="json")

    def test_registrar_producto_en_bodega_con_cantidad_cero(self):
        r = self.registrar()
        self.assertEqual(r.status_code, 201)
        cuerpo = r.json()
        self.assertEqual(cuerpo["cantidad"], 0)
        self.assertEqual(cuerpo["stock_minimo"], 100)
        self.assertTrue(cuerpo["bajo_minimo"])
        self.assertIsInstance(cuerpo["cantidad"], (int, float))  # number, no string

    def test_registro_duplicado_409(self):
        self.registrar()
        r = self.registrar()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "PRODUCTO_YA_REGISTRADO")

    def test_bodega_inexistente_o_inactiva_400(self):
        self.assertEqual(self.registrar(bodega_id=999).status_code, 400)
        inactiva = self.crear_bodega("B-OFF", activa=False)
        r = self.registrar(bodega_id=inactiva.id)
        self.assertEqual(r.json()["error"], "BODEGA_INACTIVA")

    def test_maximo_menor_que_minimo_400(self):
        self.assertEqual(self.registrar(stock_minimo=100, stock_maximo=50).status_code, 400)

    def test_solo_admin_registra(self):
        r = self.operador.post(URL, {"producto_id": 1, "bodega_id": self.bodega.id, "stock_minimo": 1}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_consulta_filtra_y_marca_bajo_minimo(self):
        Existencia.objects.create(producto_id=1, bodega=self.bodega, cantidad=5, stock_minimo=10)
        Existencia.objects.create(producto_id=2, bodega=self.bodega, cantidad=50, stock_minimo=10)
        otra = self.crear_bodega("B2")
        Existencia.objects.create(producto_id=1, bodega=otra, cantidad=0, stock_minimo=0)

        self.assertEqual(len(self.operador.get(URL).json()), 3)
        self.assertEqual(len(self.operador.get(URL, {"producto_id": 1}).json()), 2)
        self.assertEqual(len(self.operador.get(URL, {"bodega_id": otra.id}).json()), 1)
        bajos = self.operador.get(URL, {"bajo_minimo": "true"}).json()
        self.assertEqual([e["producto_id"] for e in bajos], [1])
        self.assertTrue(bajos[0]["bajo_minimo"])

    def test_paginacion_y_total(self):
        for pid in range(1, 26):
            Existencia.objects.create(producto_id=pid, bodega=self.bodega, cantidad=1, stock_minimo=0)
        r = self.operador.get(URL, {"page": 2, "page_size": 10})
        self.assertEqual(len(r.json()), 10)
        self.assertEqual(r.json()[0]["producto_id"], 11)
        self.assertEqual(r["X-Total-Count"], "25")
        self.assertEqual(len(self.operador.get(URL, {"page_size": 500}).json()), 25)  # tope 100

    def test_umbral_conserva_maximo_si_no_se_envia(self):
        e = Existencia.objects.create(producto_id=1, bodega=self.bodega, cantidad=30, stock_minimo=10, stock_maximo=200)
        r = self.admin.put(f"{URL}/{e.id}/umbral", {"stock_minimo": 40}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["stock_maximo"], 200)
        self.assertTrue(r.json()["bajo_minimo"])

    def test_umbral_no_modifica_cantidad(self):
        e = Existencia.objects.create(producto_id=1, bodega=self.bodega, cantidad=30, stock_minimo=10)
        self.admin.put(f"{URL}/{e.id}/umbral", {"stock_minimo": 5, "cantidad": 999}, format="json")
        e.refresh_from_db()
        self.assertEqual(e.cantidad, Decimal("30"))

    def test_umbral_null_elimina_maximo_y_valida_rango(self):
        e = Existencia.objects.create(producto_id=1, bodega=self.bodega, cantidad=0, stock_minimo=10, stock_maximo=20)
        self.assertEqual(self.admin.put(f"{URL}/{e.id}/umbral", {"stock_minimo": 30}, format="json").status_code, 400)
        r = self.admin.put(f"{URL}/{e.id}/umbral", {"stock_minimo": 30, "stock_maximo": None}, format="json")
        self.assertIsNone(r.json()["stock_maximo"])

    def test_umbral_inexistente_404(self):
        self.assertEqual(self.admin.put(f"{URL}/999/umbral", {"stock_minimo": 1}, format="json").status_code, 404)


def respuesta(status, cuerpo=None):
    return Mock(status_code=status, json=Mock(return_value=cuerpo or {}))


@override_settings(CATALOGO_VALIDACION=True, CATALOGO_SERVICE_URL="http://catalogo/api/catalogo")
class StockConCatalogoTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.bodega = self.crear_bodega()
        self.datos = {"producto_id": 12, "bodega_id": self.bodega.id, "stock_minimo": 10}

    @patch("inventario.catalogo.requests.get")
    def test_producto_valido_agrega_nombre(self, get):
        get.return_value = respuesta(200, {"id": 12, "nombre": "Leche entera 1L", "activo": True})
        r = self.admin.post(URL, self.datos, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["producto_nombre"], "Leche entera 1L")
        get.assert_called_once_with("http://catalogo/api/catalogo/productos/12", timeout=3.0)

    @patch("inventario.catalogo.requests.get")
    def test_producto_inexistente_422(self, get):
        get.return_value = respuesta(404)
        r = self.admin.post(URL, self.datos, format="json")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"], "REFERENCIA_INVALIDA")

    @patch("inventario.catalogo.requests.get")
    def test_producto_inactivo_422(self, get):
        get.return_value = respuesta(200, {"id": 12, "nombre": "X", "activo": False})
        self.assertEqual(self.admin.post(URL, self.datos, format="json").status_code, 422)

    @patch("inventario.catalogo.requests.get", side_effect=requests.ConnectionError)
    def test_catalogo_caido_503_y_no_crea(self, _get):
        r = self.admin.post(URL, self.datos, format="json")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"], "CATALOGO_NO_DISPONIBLE")
        self.assertFalse(Existencia.objects.exists())

    @patch("inventario.catalogo.requests.get", side_effect=requests.ConnectionError)
    def test_consulta_funciona_con_catalogo_caido_sin_reintentar(self, get):
        for pid in range(1, 6):
            Existencia.objects.create(producto_id=pid, bodega=self.bodega, cantidad=1, stock_minimo=0)
        r = self.operador.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()[0]["producto_nombre"])
        self.assertEqual(get.call_count, 1)  # se detiene tras el primer fallo (RNF06)
