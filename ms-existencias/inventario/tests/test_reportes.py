from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.test import override_settings
from django.utils import timezone

from inventario.models import Existencia, Movimiento

from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/reportes"
COSTOS = {1: 1000, 2: 200.5, 3: 0}


def catalogo_falso(url, timeout):
    pid = int(url.rstrip("/").split("/")[-1])
    if pid not in COSTOS:
        return Mock(status_code=404)
    return Mock(status_code=200, json=Mock(return_value={
        "id": pid, "codigo": f"P-{pid:03d}", "nombre": f"Producto {pid}", "costo": COSTOS[pid], "activo": True}))


class ReporteExistenciasTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.b1 = self.crear_bodega("B1", nombre="Bodega Manizales")
        self.b2 = self.crear_bodega("B2", nombre="Bodega Pereira")
        Existencia.objects.create(producto_id=1, bodega=self.b1, cantidad=5, stock_minimo=10)                    # bajo
        Existencia.objects.create(producto_id=2, bodega=self.b1, cantidad=50, stock_minimo=10, stock_maximo=100)  # normal
        Existencia.objects.create(producto_id=3, bodega=self.b2, cantidad=300, stock_minimo=10, stock_maximo=100)  # sobre

    def test_estados_y_estructura(self):
        r = self.operador.get(f"{URL}/existencias").json()
        self.assertEqual(r["total_registros"], 3)
        self.assertIn("fecha_corte", r)
        self.assertEqual([i["estado"] for i in r["items"]], ["BAJO_MINIMO", "NORMAL", "SOBRESTOCK"])
        self.assertEqual(r["items"][0]["bodega_nombre"], "Bodega Manizales")
        self.assertIsNone(r["items"][0]["producto_nombre"])  # sin catálogo el reporte igual funciona

    def test_filtros(self):
        self.assertEqual(self.operador.get(f"{URL}/existencias", {"estado": "SOBRESTOCK"}).json()["total_registros"], 1)
        self.assertEqual(self.operador.get(f"{URL}/existencias", {"estado": "NORMAL"}).json()["items"][0]["producto_id"], 2)
        self.assertEqual(self.operador.get(f"{URL}/existencias", {"bodega_id": self.b1.id}).json()["total_registros"], 2)
        self.assertEqual(self.operador.get(f"{URL}/existencias", {"estado": "X"}).status_code, 400)

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get", side_effect=catalogo_falso)
    def test_enriquecido_con_catalogo(self, _get):
        item = self.operador.get(f"{URL}/existencias").json()["items"][0]
        self.assertEqual((item["producto_codigo"], item["producto_nombre"]), ("P-001", "Producto 1"))


@override_settings(CATALOGO_VALIDACION=True)
class ReporteValorizacionTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.b1 = self.crear_bodega("B1", nombre="Bodega Manizales")
        self.b2 = self.crear_bodega("B2", nombre="Bodega Pereira")
        Existencia.objects.create(producto_id=1, bodega=self.b1, cantidad=10, stock_minimo=0)   # 10 x 1000
        Existencia.objects.create(producto_id=2, bodega=self.b1, cantidad=5, stock_minimo=0)    # 5 x 200.5
        Existencia.objects.create(producto_id=1, bodega=self.b2, cantidad=2, stock_minimo=0)    # 2 x 1000
        Existencia.objects.create(producto_id=3, bodega=self.b2, cantidad=0, stock_minimo=0)    # sin saldo

    @patch("inventario.catalogo.requests.get", side_effect=catalogo_falso)
    def test_valor_total_y_por_bodega(self, _get):
        r = self.admin.get(f"{URL}/valorizacion").json()
        self.assertEqual(r["valor_total"], 13002.5)
        self.assertEqual(r["por_bodega"], [
            {"bodega_id": self.b1.id, "bodega_nombre": "Bodega Manizales", "total_productos": 2, "valor": 11002.5},
            {"bodega_id": self.b2.id, "bodega_nombre": "Bodega Pereira", "total_productos": 1, "valor": 2000.0},
        ])
        self.assertEqual(self.admin.get(f"{URL}/valorizacion", {"bodega_id": self.b2.id}).json()["valor_total"], 2000.0)

    @patch("inventario.catalogo.requests.get", side_effect=catalogo_falso)
    def test_producto_sin_registro_en_catalogo_vale_cero(self, _get):
        Existencia.objects.create(producto_id=99, bodega=self.b1, cantidad=7, stock_minimo=0)
        self.assertEqual(self.admin.get(f"{URL}/valorizacion").json()["valor_total"], 13002.5)

    @patch("inventario.catalogo.requests.get", side_effect=requests.ConnectionError)
    def test_catalogo_caido_503(self, _get):
        r = self.admin.get(f"{URL}/valorizacion")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"], "CATALOGO_NO_DISPONIBLE")

    @override_settings(CATALOGO_VALIDACION=False)
    def test_sin_catalogo_configurado_503(self):
        self.assertEqual(self.admin.get(f"{URL}/valorizacion").status_code, 503)


class ReporteRotacionTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.b1 = self.crear_bodega("B1")
        ahora = timezone.now()
        self.desde = (timezone.localdate() - timedelta(days=20)).isoformat()
        self.hasta = timezone.localdate().isoformat()

        def kardex(pid, eventos, saldo_final):
            Existencia.objects.create(producto_id=pid, bodega=self.b1, cantidad=saldo_final, stock_minimo=0)
            for dias, tipo, cantidad, saldo in eventos:
                Movimiento.objects.create(producto_id=pid, bodega=self.b1, tipo=tipo, cantidad=cantidad,
                                          saldo_resultante=saldo, fecha=ahora - timedelta(days=dias))

        # P1: 100 al inicio del periodo, vende 40 -> promedio 80, índice 0.5
        kardex(1, [(40, "ENTRADA", 100, 100), (10, "SALIDA", 40, 60)], 60)
        # P2: 50 en stock, sin ventas -> índice 0
        kardex(2, [(40, "ENTRADA", 50, 50)], 50)
        # P3: registrado sin movimientos
        kardex(3, [], 0)
        # P4: entra y sale todo dentro del periodo -> promedio 0 con ventas (rotación máxima)
        kardex(4, [(15, "ENTRADA", 10, 10), (5, "SALIDA", 10, 0)], 0)
        # Una salida anterior al periodo no cuenta
        Movimiento.objects.create(producto_id=2, bodega=self.b1, tipo="SALIDA", cantidad=1, saldo_resultante=49,
                                  fecha=ahora - timedelta(days=60))

    def rotacion(self, **params):
        return self.admin.get(f"{URL}/rotacion", {"desde": self.desde, "hasta": self.hasta, **params})

    def test_mayor_rotacion(self):
        items = self.rotacion().json()["items"]
        self.assertEqual([i["producto_id"] for i in items[:2]], [4, 1])
        self.assertIsNone(items[0]["indice_rotacion"])
        p1 = items[1]
        self.assertEqual((p1["unidades_salida"], p1["stock_promedio"], p1["indice_rotacion"]), (40.0, 80.0, 0.5))

    def test_menor_rotacion_incluye_productos_sin_ventas(self):
        cuerpo = self.rotacion(orden="MENOR", limite=2).json()
        self.assertEqual(cuerpo["orden"], "MENOR")
        self.assertEqual(len(cuerpo["items"]), 2)
        self.assertTrue({i["producto_id"] for i in cuerpo["items"]} <= {2, 3})
        self.assertEqual(cuerpo["items"][0]["unidades_salida"], 0.0)

    def test_validaciones(self):
        self.assertEqual(self.admin.get(f"{URL}/rotacion", {"hasta": self.hasta}).status_code, 400)
        self.assertEqual(self.rotacion(desde=self.hasta, hasta=self.desde).status_code, 400)
        self.assertEqual(self.rotacion(orden="ALTA").status_code, 400)
        self.assertEqual(len(self.rotacion(limite=500).json()["items"]), 4)  # tope 100
