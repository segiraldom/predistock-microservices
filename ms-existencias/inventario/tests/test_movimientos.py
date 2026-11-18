import threading
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TransactionTestCase, override_settings

from inventario.models import Bodega, Existencia, Lote, Movimiento

from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/movimientos"
HOY = date.today()


class MovimientosBase(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.bodega = self.crear_bodega()  # id 1 = bodega del operador
        self.existencia = Existencia.objects.create(producto_id=12, bodega=self.bodega, cantidad=0, stock_minimo=10)

    def mover(self, tipo, cantidad, cliente=None, **extra):
        datos = {"producto_id": 12, "bodega_id": self.bodega.id, "tipo": tipo, "cantidad": cantidad}
        datos.update(extra)
        return (cliente or self.admin).post(URL, datos, format="json")

    def saldo(self):
        self.existencia.refresh_from_db()
        return self.existencia.cantidad


class SaldoTest(MovimientosBase):
    def test_entrada_suma_y_registra_auditoria(self):
        r = self.mover("ENTRADA", 100)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["saldo_resultante"], 100)
        self.assertEqual(r.json()["usuario_id"], 1)
        self.assertEqual(self.saldo(), 100)

    def test_salida_resta(self):
        self.mover("ENTRADA", 100)
        r = self.mover("SALIDA", 30)
        self.assertEqual(r.json()["saldo_resultante"], 70)
        self.assertEqual(self.saldo(), 70)

    def test_stock_insuficiente_409_sin_cambios(self):
        self.mover("ENTRADA", 80)
        r = self.mover("SALIDA", 120)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {"error": "STOCK_INSUFICIENTE",
                                    "mensaje": "Disponible 80, solicitado 120 (producto 12, bodega 1)"})
        self.assertEqual(self.saldo(), 80)
        self.assertEqual(Movimiento.objects.count(), 1)

    def test_ajustes_requieren_motivo(self):
        self.assertEqual(self.mover("AJUSTE_ENTRADA", 5).status_code, 400)
        self.assertEqual(self.mover("AJUSTE_ENTRADA", 5, motivo="Conteo físico").status_code, 201)
        self.assertEqual(self.mover("AJUSTE_SALIDA", 2, motivo="Producto dañado").json()["saldo_resultante"], 3)

    def test_tipos_de_documento_no_se_registran_aqui(self):
        self.assertEqual(self.mover("TRASLADO_SALIDA", 1).status_code, 400)

    def test_cantidad_debe_ser_positiva(self):
        self.assertEqual(self.mover("ENTRADA", 0).status_code, 400)
        self.assertEqual(self.mover("ENTRADA", -5).status_code, 400)

    def test_producto_no_registrado_422(self):
        r = self.mover("ENTRADA", 5, producto_id=99)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"], "PRODUCTO_NO_REGISTRADO")

    def test_bodega_inactiva_400(self):
        self.bodega.activa = False
        self.bodega.save()
        self.assertEqual(self.mover("ENTRADA", 5).json()["error"], "BODEGA_INACTIVA")

    def test_kardex_no_se_modifica_ni_elimina(self):
        self.mover("ENTRADA", 5)
        m = Movimiento.objects.get()
        m.cantidad = 1
        with self.assertRaises(PermissionDenied):
            m.save()
        with self.assertRaises(PermissionDenied):
            m.delete()


class PermisosTest(MovimientosBase):
    def test_operador_en_su_bodega(self):
        self.assertEqual(self.mover("ENTRADA", 5, cliente=self.operador).status_code, 201)

    def test_operador_en_otra_bodega_403(self):
        otra = self.crear_bodega("B2")
        Existencia.objects.create(producto_id=12, bodega=otra, cantidad=0, stock_minimo=0)
        r = self.mover("ENTRADA", 5, cliente=self.operador, bodega_id=otra.id)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "BODEGA_NO_ASIGNADA")

    def test_operador_sin_bodega_403(self):
        self.assertEqual(self.mover("ENTRADA", 5, cliente=self.cliente("OPERADOR_BODEGA")).status_code, 403)

    def test_analista_no_registra(self):
        self.assertEqual(self.mover("ENTRADA", 5, cliente=self.cliente("ANALISTA")).status_code, 403)


class LotesFEFOTest(MovimientosBase):
    def entrada_lote(self, numero, vence, cantidad):
        return self.mover("ENTRADA", cantidad, numero_lote=numero, fecha_vencimiento=vence.isoformat())

    def test_entrada_crea_lote_y_otra_entrada_lo_acumula(self):
        r = self.entrada_lote("L-1", HOY + timedelta(days=30), 50)
        self.assertIsNotNone(r.json()["lote_id"])
        self.entrada_lote("L-1", HOY + timedelta(days=30), 20)
        self.assertEqual(Lote.objects.get().cantidad, 70)

    def test_mismo_lote_con_otra_fecha_400(self):
        self.entrada_lote("L-1", HOY + timedelta(days=30), 50)
        r = self.entrada_lote("L-1", HOY + timedelta(days=40), 5)
        self.assertEqual(r.json()["error"], "LOTE_INCONSISTENTE")

    def test_numero_lote_sin_fecha_400(self):
        self.assertEqual(self.mover("ENTRADA", 5, numero_lote="L-1").status_code, 400)

    def test_salida_fefo_consume_primero_el_que_vence_antes(self):
        self.entrada_lote("TARDE", HOY + timedelta(days=60), 50)
        self.entrada_lote("PRONTO", HOY + timedelta(days=10), 30)
        r = self.mover("SALIDA", 40)
        self.assertEqual(r.status_code, 201)
        ids = r["X-Movimientos-Ids"].split(",")
        self.assertEqual(len(ids), 2)  # un movimiento por lote consumido
        self.assertEqual(Lote.objects.get(numero_lote="PRONTO").cantidad, 0)
        self.assertEqual(Lote.objects.get(numero_lote="TARDE").cantidad, 40)
        self.assertEqual(r.json()["saldo_resultante"], 40)
        self.assertEqual(self.saldo(), 40)

    def test_salida_no_despacha_lotes_vencidos(self):
        self.entrada_lote("VENCIDO", HOY - timedelta(days=1), 20)
        r = self.mover("SALIDA", 5)
        self.assertEqual(r.status_code, 409)
        self.assertIn("lotes vigentes", r.json()["mensaje"])
        # la baja del vencido se hace con un ajuste
        self.assertEqual(self.mover("AJUSTE_SALIDA", 20, motivo="Vencido").status_code, 201)
        self.assertEqual(Lote.objects.get().cantidad, 0)

    def test_salida_de_un_lote_especifico(self):
        a = Lote.objects.get(pk=self.entrada_lote("A", HOY + timedelta(days=5), 10).json()["lote_id"])
        b = Lote.objects.get(pk=self.entrada_lote("B", HOY + timedelta(days=50), 10).json()["lote_id"])
        self.mover("SALIDA", 4, lote_id=b.id)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.cantidad, b.cantidad), (10, 6))
        self.assertEqual(self.mover("SALIDA", 7, lote_id=b.id).status_code, 409)

    def test_lote_de_otro_producto_400(self):
        Existencia.objects.create(producto_id=13, bodega=self.bodega, cantidad=0, stock_minimo=0)
        otro = self.mover("ENTRADA", 5, producto_id=13, numero_lote="X", fecha_vencimiento="2030-01-01").json()
        self.entrada_lote("L", HOY + timedelta(days=5), 5)
        self.assertEqual(self.mover("SALIDA", 1, lote_id=otro["lote_id"]).json()["error"], "LOTE_INVALIDO")

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get")
    def test_perecedero_segun_catalogo_exige_lote(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"id": 12, "activo": True, "es_perecedero": True}))
        r = self.mover("ENTRADA", 10)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "LOTE_REQUERIDO")

    @override_settings(CATALOGO_VALIDACION=True)
    @patch("inventario.catalogo.requests.get", side_effect=requests.ConnectionError)
    def test_movimiento_funciona_con_catalogo_caido(self, _get):
        self.assertEqual(self.mover("ENTRADA", 10).status_code, 201)


@patch("inventario.notificaciones.requests.post")
class AlertasTest(MovimientosBase):
    def test_alerta_cuando_queda_bajo_el_minimo(self, post):
        post.return_value = Mock(status_code=200)
        self.mover("ENTRADA", 15)
        with self.captureOnCommitCallbacks(execute=True):
            self.mover("SALIDA", 11)
        post.assert_called_once()
        url, datos = post.call_args.args[0], post.call_args.kwargs["json"]
        self.assertEqual(url, "http://notif/api/notifications/alerts")
        self.assertEqual(datos["alert_type"], "LOW_STOCK_THRESHOLD")
        self.assertEqual((datos["product_id"], datos["warehouse_id"]), (12, self.bodega.id))
        self.assertEqual((datos["current_stock"], datos["threshold"]), (4, 10))

    def test_sin_alerta_si_sigue_sobre_el_minimo_o_es_entrada(self, post):
        with self.captureOnCommitCallbacks(execute=True):
            self.mover("ENTRADA", 50)
            self.mover("SALIDA", 5)
        post.assert_not_called()

    def test_sin_alerta_si_el_movimiento_falla(self, post):
        with self.captureOnCommitCallbacks(execute=True):
            self.mover("SALIDA", 5)  # 409
        post.assert_not_called()

    def test_notificaciones_caido_no_afecta_el_movimiento(self, post):
        post.side_effect = requests.ConnectionError
        self.mover("ENTRADA", 15)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.mover("SALIDA", 11)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.saldo(), 4)


class KardexTest(MovimientosBase):
    def test_kardex_ordenado_y_filtrado(self):
        self.mover("ENTRADA", 10)
        self.mover("SALIDA", 3, cliente=self.operador)
        datos = self.admin.get(URL).json()
        self.assertEqual([m["tipo"] for m in datos], ["SALIDA", "ENTRADA"])
        self.assertEqual(len(self.admin.get(URL, {"tipo": "ENTRADA"}).json()), 1)
        self.assertEqual(len(self.admin.get(URL, {"usuario_id": 2}).json()), 1)
        self.assertEqual(len(self.admin.get(URL, {"desde": HOY.isoformat(), "hasta": HOY.isoformat()}).json()), 2)
        self.assertEqual(len(self.admin.get(URL, {"hasta": (HOY - timedelta(days=1)).isoformat()}).json()), 0)

    def test_filtros_invalidos_400(self):
        self.assertEqual(self.admin.get(URL, {"tipo": "ROBO"}).status_code, 400)
        self.assertEqual(self.admin.get(URL, {"desde": "18/11/2026"}).status_code, 400)

    def test_historico_para_analitica(self):
        self.mover("ENTRADA", 10)
        self.mover("SALIDA", 3)
        cuerpo = self.admin.get(f"{URL}/historico").json()
        self.assertEqual(cuerpo["total"], 2)
        salida = cuerpo["data"][1]
        self.assertEqual(set(salida), {"id", "producto_id", "bodega_id", "tipo", "cantidad", "fecha"})
        self.assertEqual(salida["tipo"], "SALIDA_VENTA")
        self.assertEqual(salida["cantidad"], 3.0)
        self.assertRegex(salida["fecha"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class LotesEndpointTest(MovimientosBase):
    def setUp(self):
        super().setUp()
        self.lote_pronto = Lote.objects.create(producto_id=12, bodega=self.bodega, numero_lote="A",
                                               fecha_vencimiento=HOY + timedelta(days=5), cantidad=10)
        Lote.objects.create(producto_id=12, bodega=self.bodega, numero_lote="B",
                            fecha_vencimiento=HOY + timedelta(days=90), cantidad=10)
        Lote.objects.create(producto_id=12, bodega=self.bodega, numero_lote="C",
                            fecha_vencimiento=HOY + timedelta(days=1), cantidad=0)

    def test_listado_por_vencimiento_y_saldo(self):
        self.assertEqual([l["numero_lote"] for l in self.operador.get(f"{PREFIJO}/lotes").json()], ["A", "B"])
        proximos = self.operador.get(f"{PREFIJO}/lotes", {"vence_antes_de": (HOY + timedelta(days=10)).isoformat()})
        self.assertEqual([l["numero_lote"] for l in proximos.json()], ["A"])
        self.assertEqual(len(self.operador.get(f"{PREFIJO}/lotes", {"con_saldo": "false"}).json()), 3)

    def test_corregir_fecha(self):
        r = self.admin.patch(f"{PREFIJO}/lotes/{self.lote_pronto.id}", {"fecha_vencimiento": "2030-01-01"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fecha_vencimiento"], "2030-01-01")

    def test_no_permite_cambiar_cantidad(self):
        r = self.admin.patch(f"{PREFIJO}/lotes/{self.lote_pronto.id}", {"cantidad": 999}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "CAMPO_NO_EDITABLE")
        self.lote_pronto.refresh_from_db()
        self.assertEqual(self.lote_pronto.cantidad, 10)

    def test_numero_duplicado_y_permisos(self):
        url = f"{PREFIJO}/lotes/{self.lote_pronto.id}"
        self.assertEqual(self.admin.patch(url, {"numero_lote": "B"}, format="json").status_code, 400)
        self.assertEqual(self.operador.patch(url, {"numero_lote": "Z"}, format="json").status_code, 403)
        self.assertEqual(self.admin.patch(f"{PREFIJO}/lotes/999", {"numero_lote": "Z"}, format="json").status_code, 404)


@unittest.skipUnless(connection.vendor == "postgresql", "El bloqueo de fila solo se prueba con PostgreSQL")
@override_settings(CATALOGO_VALIDACION=False, NOTIFICACIONES_SERVICE_URL="")
class ConcurrenciaTest(TransactionTestCase):
    """Dos salidas simultáneas de 60 sobre un saldo de 100: solo una debe pasar (SELECT FOR UPDATE)."""

    def test_salidas_simultaneas_no_dejan_saldo_negativo(self):
        from rest_framework.test import APIClient
        bodega = Bodega.objects.create(codigo="B", nombre="B", region="R")
        existencia = Existencia.objects.create(producto_id=1, bodega=bodega, cantidad=100, stock_minimo=0)
        resultados, barrera = [], threading.Barrier(2)

        def salida():
            c = APIClient()
            c.credentials(HTTP_X_ROL="ADMIN", HTTP_X_USUARIO_ID="1")
            barrera.wait()
            resultados.append(c.post(URL, {"producto_id": 1, "bodega_id": bodega.id, "tipo": "SALIDA",
                                           "cantidad": 60}, format="json").status_code)
            connection.close()

        hilos = [threading.Thread(target=salida) for _ in range(2)]
        for h in hilos: h.start()
        for h in hilos: h.join()

        existencia.refresh_from_db()
        self.assertEqual(sorted(resultados), [201, 409])
        self.assertEqual(existencia.cantidad, Decimal("40"))
