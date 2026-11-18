from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests
from django.test import override_settings

from inventario.models import Existencia, Lote, Movimiento, OrdenCompra

from .base import PREFIJO, BaseAPITest

HOY = date.today()


class DocumentosBase(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.b1 = self.crear_bodega("B1")  # bodega del operador
        self.b2 = self.crear_bodega("B2", nombre="Bodega Pereira")

    def stock(self, producto_id, bodega, cantidad=0, minimo=0):
        return Existencia.objects.create(producto_id=producto_id, bodega=bodega, cantidad=cantidad, stock_minimo=minimo)

    @staticmethod
    def saldo(producto_id, bodega):
        e = Existencia.objects.filter(producto_id=producto_id, bodega=bodega).first()
        return e.cantidad if e else None


# ---------------- Traslados ----------------

class TrasladosTest(DocumentosBase):
    URL = f"{PREFIJO}/traslados"

    def trasladar(self, detalle, cliente=None, origen=None, destino=None, **extra):
        datos = {"bodega_origen_id": (origen or self.b1).id, "bodega_destino_id": (destino or self.b2).id,
                 "detalle": detalle, **extra}
        return (cliente or self.admin).post(self.URL, datos, format="json")

    def test_traslado_mueve_stock_y_genera_dos_movimientos_por_producto(self):
        self.stock(12, self.b1, 100)
        r = self.trasladar([{"producto_id": 12, "cantidad": 30}], sugerencia_id=14)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["sugerencia_id"], 14)
        self.assertEqual(r.json()["detalle"], [{"producto_id": 12, "cantidad": 30}])
        self.assertEqual(self.saldo(12, self.b1), 70)
        self.assertEqual(self.saldo(12, self.b2), 30)  # se registra sola en destino
        tipos = set(Movimiento.objects.filter(traslado_id=r.json()["id"]).values_list("tipo", flat=True))
        self.assertEqual(tipos, {"TRASLADO_SALIDA", "TRASLADO_ENTRADA"})

    def test_traslado_es_atomico(self):
        self.stock(1, self.b1, 50)
        self.stock(2, self.b1, 5)
        r = self.trasladar([{"producto_id": 1, "cantidad": 10}, {"producto_id": 2, "cantidad": 10}])
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.saldo(1, self.b1), 50)  # el primer producto tampoco se movió
        self.assertFalse(Movimiento.objects.exists())

    def test_lote_viaja_con_la_mercancia(self):
        self.stock(12, self.b1, 0)
        vence = HOY + timedelta(days=20)
        self.admin.post(f"{PREFIJO}/movimientos", {"producto_id": 12, "bodega_id": self.b1.id, "tipo": "ENTRADA",
                        "cantidad": 40, "numero_lote": "L-9", "fecha_vencimiento": vence.isoformat()}, format="json")
        self.trasladar([{"producto_id": 12, "cantidad": 15}])
        lote_destino = Lote.objects.get(bodega=self.b2)
        self.assertEqual((lote_destino.numero_lote, lote_destino.fecha_vencimiento, lote_destino.cantidad),
                         ("L-9", vence, 15))
        self.assertEqual(Lote.objects.get(bodega=self.b1).cantidad, 25)

    def test_validaciones(self):
        self.stock(12, self.b1, 10)
        self.assertEqual(self.trasladar([{"producto_id": 12, "cantidad": 1}], destino=self.b1).status_code, 400)
        self.assertEqual(self.trasladar([]).status_code, 400)
        repetido = [{"producto_id": 12, "cantidad": 1}, {"producto_id": 12, "cantidad": 2}]
        self.assertEqual(self.trasladar(repetido).status_code, 400)

    def test_operador_despacha_solo_desde_su_bodega(self):
        self.stock(12, self.b1, 10)
        self.stock(12, self.b2, 10)
        linea = [{"producto_id": 12, "cantidad": 1}]
        self.assertEqual(self.trasladar(linea, cliente=self.operador).status_code, 201)
        r = self.trasladar(linea, cliente=self.operador, origen=self.b2, destino=self.b1)
        self.assertEqual(r.status_code, 403)

    def test_consulta(self):
        self.stock(12, self.b1, 10)
        tid = self.trasladar([{"producto_id": 12, "cantidad": 1}]).json()["id"]
        self.assertEqual(self.operador.get(f"{self.URL}/{tid}").json()["bodega_destino_id"], self.b2.id)
        self.assertEqual(len(self.operador.get(self.URL, {"bodega_origen_id": self.b1.id}).json()), 1)
        self.assertEqual(len(self.operador.get(self.URL, {"bodega_origen_id": self.b2.id}).json()), 0)
        self.assertEqual(self.operador.get(f"{self.URL}/999").status_code, 404)


# ---------------- Devoluciones ----------------

class DevolucionesTest(DocumentosBase):
    URL = f"{PREFIJO}/devoluciones"

    def devolver(self, tipo, detalle, cliente=None, **extra):
        datos = {"tipo": tipo, "bodega_id": self.b1.id, "motivo": "Empaque defectuoso", "detalle": detalle, **extra}
        return (cliente or self.operador).post(self.URL, datos, format="json")

    def test_cliente_solo_aptos_vuelven_al_stock(self):
        self.stock(12, self.b1, 10)
        r = self.devolver("CLIENTE", [{"producto_id": 12, "cantidad": 5, "condicion": "APTO"},
                                      {"producto_id": 12, "cantidad": 3, "condicion": "AVERIADO"}],
                          referencia_cliente="F-123")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.json()["detalle"]), 2)
        self.assertEqual(self.saldo(12, self.b1), 15)
        self.assertEqual(Movimiento.objects.get().tipo, "DEVOLUCION_CLIENTE")

    def test_proveedor_resta_del_stock(self):
        self.stock(12, self.b1, 10)
        r = self.devolver("PROVEEDOR", [{"producto_id": 12, "cantidad": 4, "condicion": "AVERIADO"}], proveedor_id=5)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.saldo(12, self.b1), 6)

    def test_proveedor_sin_stock_suficiente_409_y_no_queda_registro(self):
        self.stock(12, self.b1, 2)
        r = self.devolver("PROVEEDOR", [{"producto_id": 12, "cantidad": 4, "condicion": "APTO"}], proveedor_id=5)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.operador.get(self.URL).json(), [])

    def test_proveedor_puede_llevarse_lotes_vencidos(self):
        self.stock(12, self.b1, 10)
        Lote.objects.create(producto_id=12, bodega=self.b1, numero_lote="V", fecha_vencimiento=HOY - timedelta(days=3),
                            cantidad=10)
        r = self.devolver("PROVEEDOR", [{"producto_id": 12, "cantidad": 10, "condicion": "AVERIADO"}], proveedor_id=5)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lote.objects.get().cantidad, 0)

    def test_validaciones(self):
        self.stock(12, self.b1, 10)
        linea = [{"producto_id": 12, "cantidad": 1, "condicion": "APTO"}]
        self.assertEqual(self.devolver("PROVEEDOR", linea).status_code, 400)  # falta proveedor_id
        self.assertEqual(self.devolver("CLIENTE", [{**linea[0], "condicion": "ROTO"}]).status_code, 400)
        self.assertEqual(self.devolver("CLIENTE", [{"producto_id": 99, "cantidad": 1, "condicion": "APTO"}]).status_code, 422)

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get")
    def test_proveedor_inexistente_422(self, get):
        get.return_value = Mock(status_code=404)
        self.stock(12, self.b1, 10)
        r = self.devolver("PROVEEDOR", [{"producto_id": 12, "cantidad": 1, "condicion": "APTO"}], proveedor_id=77)
        self.assertEqual(r.status_code, 422)
        self.assertIn("proveedor 77", r.json()["mensaje"])

    def test_filtros(self):
        self.stock(12, self.b1, 10)
        self.devolver("CLIENTE", [{"producto_id": 12, "cantidad": 1, "condicion": "APTO"}])
        self.devolver("PROVEEDOR", [{"producto_id": 12, "cantidad": 1, "condicion": "APTO"}], proveedor_id=5)
        self.assertEqual(len(self.admin.get(self.URL, {"tipo": "PROVEEDOR"}).json()), 1)
        self.assertEqual(len(self.admin.get(self.URL, {"proveedor_id": 5}).json()), 1)
        did = self.admin.get(self.URL).json()[0]["id"]
        self.assertEqual(self.admin.get(f"{self.URL}/{did}").status_code, 200)


# ---------------- Órdenes de compra ----------------

class OrdenesTest(DocumentosBase):
    URL = f"{PREFIJO}/ordenes-compra"

    def crear_orden(self, detalle=None, cliente=None):
        detalle = detalle or [{"producto_id": 12, "cantidad_solicitada": 300, "precio_unitario": 3200},
                              {"producto_id": 13, "cantidad_solicitada": 50, "precio_unitario": 1000}]
        return (cliente or self.admin).post(self.URL, {"proveedor_id": 5, "bodega_id": self.b1.id, "detalle": detalle},
                                            format="json")

    def recibir(self, orden, lineas, cliente=None):
        return (cliente or self.operador).post(f"{self.URL}/{orden['id']}/recepciones", {"lineas": lineas}, format="json")

    def test_crear_orden_pendiente_sin_mover_stock(self):
        r = self.crear_orden()
        self.assertEqual(r.status_code, 201)
        orden = r.json()
        self.assertEqual(orden["estado"], "PENDIENTE")
        self.assertRegex(orden["numero"], r"^OC-\d{4}-\d{4}$")
        self.assertEqual(orden["creada_por"], 1)
        self.assertEqual(len(orden["detalle"]), 2)
        self.assertFalse(Movimiento.objects.exists())

    def test_solo_admin_crea(self):
        self.assertEqual(self.crear_orden(cliente=self.operador).status_code, 403)

    def test_recepcion_parcial_y_luego_total(self):
        orden = self.crear_orden().json()
        l12, l13 = orden["detalle"]
        r = self.recibir(orden, [{"detalle_id": l12["id"], "cantidad": 200}])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["estado"], "PARCIAL")
        self.assertEqual(r.json()["detalle"][0]["cantidad_recibida"], 200)
        self.assertEqual(self.saldo(12, self.b1), 200)  # se registró sola en la bodega

        r = self.recibir(orden, [{"detalle_id": l12["id"], "cantidad": 100}, {"detalle_id": l13["id"], "cantidad": 50}])
        self.assertEqual(r.json()["estado"], "RECIBIDA")
        movs = Movimiento.objects.filter(orden_compra_id=orden["id"])
        self.assertEqual(movs.count(), 3)
        self.assertTrue(all(m.tipo == "ENTRADA" for m in movs))

    def test_no_recibe_mas_de_lo_pendiente(self):
        orden = self.crear_orden().json()
        r = self.recibir(orden, [{"detalle_id": orden["detalle"][1]["id"], "cantidad": 51}])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "CANTIDAD_EXCEDIDA")

    def test_linea_de_otra_orden_400(self):
        orden = self.crear_orden().json()
        otra = self.crear_orden().json()
        r = self.recibir(orden, [{"detalle_id": otra["detalle"][0]["id"], "cantidad": 1}])
        self.assertEqual(r.status_code, 400)

    def test_recepcion_con_lote(self):
        orden = self.crear_orden().json()
        self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 10,
                              "numero_lote": "L-778", "fecha_vencimiento": "2030-11-30"}])
        self.assertEqual(Lote.objects.get().cantidad, 10)

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get")
    def test_perecedero_sin_lote_400(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"id": 1, "activo": True, "es_perecedero": True}))
        orden = self.crear_orden().json()
        r = self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 10}])
        self.assertEqual(r.json()["error"], "LOTE_REQUERIDO")

    def test_operador_de_otra_bodega_no_recibe(self):
        orden = self.crear_orden().json()
        otro = self.cliente("OPERADOR_BODEGA", usuario_id=9, bodega_id=self.b2.id)
        self.assertEqual(self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 1}], otro).status_code, 403)

    def test_cancelar(self):
        orden = self.crear_orden().json()
        url = f"{self.URL}/{orden['id']}/estado"
        self.assertEqual(self.admin.patch(url, {"estado": "RECIBIDA"}, format="json").status_code, 400)
        r = self.admin.patch(url, {"estado": "CANCELADA"}, format="json")
        self.assertEqual(r.json()["estado"], "CANCELADA")
        # una orden cancelada no recibe mercancía
        self.assertEqual(self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 1}]).status_code, 409)

    def test_no_se_cancela_una_orden_con_recepciones(self):
        orden = self.crear_orden().json()
        self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 1}])
        r = self.admin.patch(f"{self.URL}/{orden['id']}/estado", {"estado": "CANCELADA"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_orden_recibida_no_admite_mas_recepciones(self):
        orden = self.crear_orden([{"producto_id": 12, "cantidad_solicitada": 5, "precio_unitario": 1}]).json()
        self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 5}])
        self.assertEqual(self.recibir(orden, [{"detalle_id": orden["detalle"][0]["id"], "cantidad": 1}]).status_code, 409)

    def test_consulta_y_filtros(self):
        oid = self.crear_orden().json()["id"]
        self.assertEqual(self.operador.get(f"{self.URL}/{oid}").json()["id"], oid)
        self.assertEqual(len(self.operador.get(self.URL, {"estado": "PENDIENTE"}).json()), 1)
        self.assertEqual(len(self.operador.get(self.URL, {"estado": "RECIBIDA"}).json()), 0)
        self.assertEqual(self.operador.get(self.URL, {"estado": "OTRO"}).status_code, 400)
        self.assertEqual(self.operador.get(f"{self.URL}/999").status_code, 404)

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get", side_effect=requests.ConnectionError)
    def test_catalogo_caido_no_crea_orden(self, _get):
        self.assertEqual(self.crear_orden().status_code, 503)
        self.assertFalse(OrdenCompra.objects.exists())
