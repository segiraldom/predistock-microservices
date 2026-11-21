"""
Siembra existencias de demostración: 3 bodegas, 30 series producto-bodega con 12 meses de kardex
(más órdenes de compra, traslados y devoluciones) y un estado final con quiebres, sobrestock y
productos en nivel óptimo. Está pensado para alimentar a ms-analitica y el dashboard.

Todo pasa por los endpoints reales del servicio (cliente de pruebas de Django, en el mismo proceso
y como ADMIN), así que se aplican las mismas reglas del kardex: saldos, lotes, FEFO, alertas.
Lo único que se escribe directamente es la fecha de cada registro (UPDATE), porque la API no
acepta fechas pasadas.

Requiere haber ejecutado antes `seed_catalogo` en ms-catalogo.

    python manage.py seed_existencias              # solo describe lo que haría
    python manage.py seed_existencias --confirmo   # ejecuta
    python manage.py seed_existencias --confirmo --hasta 2026-10-31   # cierra el histórico en esa fecha
    python manage.py seed_existencias --confirmo --solo-si-vacio      # como en docker compose: no hace nada si ya hay datos

Los movimientos no se borran: si ya hay movimientos, el comando se detiene con error (o termina en
silencio con --solo-si-vacio). Para repetir desde cero hay que recrear el volumen de la base de existencias.
"""
import math
import random
import time
from datetime import date, datetime, timedelta, time as hora
from decimal import Decimal

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.test import Client
from django.utils import timezone

from inventario.models import Devolucion, Existencia, Lote, Movimiento, OrdenCompra, Traslado

CABECERAS = {"X-Rol": "ADMIN", "X-Usuario-Id": "1", "X-Bodega-Id": "1"}
BASE = "/api/existencias"

# (código, nombre, región, ciudad, peso de demanda)
BODEGAS = [
    ("SEED-B1", "Bodega Principal", "Centro", "Bogotá", 1.25),
    ("SEED-B2", "Bodega Intermedia", "Antioquia", "Medellín", 1.00),
    ("SEED-B3", "Bodega Menor", "Occidente", "Cali", 0.80),
]

# código de producto -> (demanda semanal base, prob. de venta por semana, ventas por semana,
#                        perecedero, vida útil del lote en días)
PERFIL = {
    "PRD-001": (160, 0.95, 3, True, 45),    # alta rotación
    "PRD-002": (140, 0.90, 3, False, 0),
    "PRD-003": (120, 0.85, 3, False, 0),
    "PRD-004": (50, 0.65, 2, True, 60),     # media rotación
    "PRD-005": (45, 0.60, 2, False, 0),
    "PRD-006": (40, 0.55, 2, False, 0),
    "PRD-007": (35, 0.50, 2, False, 0),
    "PRD-008": (8, 0.25, 1, False, 0),      # baja rotación
    "PRD-009": (6, 0.20, 1, False, 0),
    "PRD-010": (4, 0.15, 1, True, 90),
}

# Estado final deseado (código de producto, índice de bodega 0..2)
QUIEBRE = {("PRD-002", 2), ("PRD-003", 1), ("PRD-005", 0), ("PRD-007", 2), ("PRD-006", 1), ("PRD-004", 2)}
SOBRESTOCK = {("PRD-008", 0), ("PRD-009", 1), ("PRD-010", 2), ("PRD-007", 0), ("PRD-005", 2), ("PRD-002", 0)}

NIT_ANDINA, NIT_LACTEOS, NIT_ASEO, NIT_PAPEL = "900100200-1", "900200300-2", "900300400-3", "900400500-4"


def estacionalidad(mes):
    if mes in (11, 12):
        return 1.30
    if mes in (6, 7):
        return 1.15
    return 1.0


def redondear_arriba(valor, multiplo=10):
    return int(math.ceil(valor / multiplo) * multiplo)


def con_hora(dia, h, m=0):
    return timezone.make_aware(datetime.combine(dia, hora(h, m)))


class Api:
    def __init__(self):
        self.client = Client(raise_request_exception=False)

    def _verificar(self, resp, esperado, ruta):
        if resp.status_code not in esperado:
            raise CommandError(f"{ruta} -> {resp.status_code}: {resp.content.decode()[:400]}")
        return resp

    def get(self, ruta, **params):
        r = self._verificar(self.client.get(f"{BASE}{ruta}", params, headers=CABECERAS), (200,), ruta)
        return r.json()

    def post(self, ruta, datos, esperado=(201,)):
        r = self.client.post(f"{BASE}{ruta}", datos, content_type="application/json", headers=CABECERAS)
        return self._verificar(r, esperado, ruta)

    def put(self, ruta, datos):
        r = self.client.put(f"{BASE}{ruta}", datos, content_type="application/json", headers=CABECERAS)
        return self._verificar(r, (200,), ruta)

    def patch(self, ruta, datos):
        r = self.client.patch(f"{BASE}{ruta}", datos, content_type="application/json", headers=CABECERAS)
        return self._verificar(r, (200,), ruta)


class Command(BaseCommand):
    help = "Siembra existencias de demostración con 12 meses de kardex para ms-analitica y el dashboard."

    def add_arguments(self, parser):
        parser.add_argument("--confirmo", action="store_true", help="Ejecuta la siembra (sin esto solo la describe)")
        parser.add_argument("--hasta", help="Último día del histórico (AAAA-MM-DD). Por defecto, ayer.")
        parser.add_argument("--semilla", type=int, default=42, help="Semilla del generador aleatorio")
        parser.add_argument("--solo-si-vacio", action="store_true", dest="solo_si_vacio",
                            help="Si ya hay movimientos, termina sin error y sin tocar nada (para ejecutarlo en cada arranque)")

    # ------------------------------------------------------------------ utilidades

    def perecedero(self, codigo):
        return PERFIL[codigo][3]

    def sync(self):
        """Relee los saldos reales de la base (autoridad) para no arrastrar diferencias en memoria."""
        for e in Existencia.objects.all():
            codigo, idx = self.clave_inversa[(e.producto_id, e.bodega_id)]
            self.stock[(codigo, idx)] = e.cantidad

    def _mov(self, serie, tipo, cantidad, fecha, motivo=None, lote_id=None, numero_lote=None, vence=None):
        codigo, idx = serie
        datos = {"producto_id": self.pid[codigo], "bodega_id": self.bid[idx], "tipo": tipo, "cantidad": str(cantidad)}
        if lote_id:
            datos["lote_id"] = lote_id
        if numero_lote:
            datos["numero_lote"] = numero_lote
            datos["fecha_vencimiento"] = vence.isoformat()
        if motivo:
            datos["motivo"] = motivo
        resp = self.api.post("/movimientos", datos)
        ids = [int(x) for x in resp["X-Movimientos-Ids"].split(",")]
        Movimiento.objects.filter(pk__in=ids).update(fecha=fecha)
        self.stock[serie] = Decimal(str(resp.json()["saldo_resultante"]))
        self.n_movimientos += 1
        return resp

    def entrar(self, serie, cantidad, fecha, motivo="Reposición programada", vida=None, numero=None):
        codigo, idx = serie
        if self.perecedero(codigo):
            vida = vida if vida is not None else PERFIL[codigo][4]
            numero = numero or f"L{codigo[-3:]}B{idx + 1}-{fecha:%y%m%d}"
            while numero in self.lotes_usados:
                numero += "x"
            self.lotes_usados.add(numero)
            self._mov(serie, "ENTRADA", cantidad, fecha, motivo, numero_lote=numero,
                      vence=fecha.date() + timedelta(days=vida))
        else:
            self._mov(serie, "ENTRADA", cantidad, fecha, motivo)

    def salir(self, serie, cantidad, fecha, tipo="SALIDA", motivo=None):
        """Salida o ajuste de salida. En perecederos consume por lote, el que vence primero (FEFO)."""
        codigo, idx = serie
        if not self.perecedero(codigo):
            self._mov(serie, tipo, cantidad, fecha, motivo)
            return
        pendiente = int(cantidad)
        lotes = Lote.objects.filter(producto_id=self.pid[codigo], bodega_id=self.bid[idx],
                                    cantidad__gt=0).order_by("fecha_vencimiento", "id")
        for lote in lotes:
            tomar = min(int(lote.cantidad), pendiente)
            if tomar <= 0:
                continue
            self._mov(serie, tipo, tomar, fecha, motivo, lote_id=lote.pk)
            pendiente -= tomar
            if pendiente <= 0:
                return
        raise CommandError(f"Sin lotes suficientes para {serie}: faltan {pendiente}")

    # ------------------------------------------------------------------ simulación

    def evento_salida(self, serie, cantidad, fecha):
        codigo, idx = serie
        base = PERFIL[codigo][0] * BODEGAS[idx][4]
        punto = math.ceil(base * 1.5)
        reposicion = redondear_arriba(base * (3 if self.perecedero(codigo) else 6))
        while self.stock[serie] < cantidad + punto:
            self.entrar(serie, reposicion, fecha - timedelta(seconds=1))
        self.salir(serie, cantidad, fecha)
        if fecha.date() > self.hasta - timedelta(days=90):
            self.demanda[serie] += cantidad

    def generar_eventos(self, rng):
        eventos = []
        inicio = self.hasta - timedelta(days=363)
        for serie in self.series:
            codigo, idx = serie
            base, freq, ntx, _, _ = PERFIL[codigo]
            peso = BODEGAS[idx][4]
            for semana in range(52):
                ini = inicio + timedelta(weeks=semana)
                if rng.random() > freq:
                    continue
                media = base * peso * estacionalidad(ini.month)
                total = max(ntx, round(rng.gauss(media, media * 0.08)))
                dias = sorted(rng.sample(range(7), ntx))
                reparto = [total // ntx + (1 if i < total % ntx else 0) for i in range(ntx)]
                for dia, parte in zip(dias, reparto):
                    d = ini + timedelta(days=dia)
                    if d > self.hasta:
                        continue
                    if rng.random() < 0.02:   # ruido atípico que el preprocesador de analítica debe filtrar
                        parte *= 3
                    eventos.append((con_hora(d, rng.randint(8, 17), rng.randint(0, 59)), "salida", serie, parte))
        return eventos

    # ------------------------------------------------------------------ documentos

    def oc_crear(self, clave, nit, idx, lineas, fecha):
        detalle = [{"producto_id": self.pid[c], "cantidad_solicitada": str(q), "precio_unitario": str(p)}
                   for c, q, p in lineas]
        orden = self.api.post("/ordenes-compra", {
            "proveedor_id": self.prov[nit], "bodega_id": self.bid[idx], "detalle": detalle}).json()
        OrdenCompra.objects.filter(pk=orden["id"]).update(fecha_emision=fecha.date())
        self.docs[clave] = orden
        self.n_docs += 1

    def oc_recibir(self, clave, cantidades, fecha):
        orden = self.docs[clave]
        por_producto = {l["producto_id"]: l for l in orden["detalle"]}
        lineas = [{"detalle_id": por_producto[self.pid[c]]["id"], "cantidad": str(q)} for c, q in cantidades.items()]
        self.api.post(f"/ordenes-compra/{orden['id']}/recepciones", {"lineas": lineas})
        Movimiento.objects.filter(orden_compra_id=orden["id"]).update(fecha=fecha)
        self.sync()

    def oc_cancelar(self, clave):
        self.api.patch(f"/ordenes-compra/{self.docs[clave]['id']}/estado", {"estado": "CANCELADA"})

    def traslado(self, origen, destino, codigo, cantidad, fecha):
        serie = (codigo, origen)
        while self.stock[serie] < cantidad + 50:
            self.entrar(serie, redondear_arriba(cantidad + 100), fecha - timedelta(seconds=1))
        t = self.api.post("/traslados", {
            "bodega_origen_id": self.bid[origen], "bodega_destino_id": self.bid[destino],
            "detalle": [{"producto_id": self.pid[codigo], "cantidad": str(cantidad)}]}).json()
        Traslado.objects.filter(pk=t["id"]).update(fecha=fecha)
        Movimiento.objects.filter(traslado_id=t["id"]).update(fecha=fecha)
        self.sync()
        self.n_docs += 1

    def devolucion(self, datos, fecha):
        d = self.api.post("/devoluciones", datos).json()
        Devolucion.objects.filter(pk=d["id"]).update(fecha=fecha)
        Movimiento.objects.filter(devolucion_id=d["id"]).update(fecha=fecha)
        self.sync()
        self.n_docs += 1

    def documentos(self, hasta):
        """(fecha, acción) de los documentos de demostración, relativos al último día del histórico."""
        def f(dias, h=12):
            return con_hora(hasta - timedelta(days=dias), h)

        return [
            (f(70), lambda fe: self.oc_crear("oc_recibida", NIT_ASEO, 1,
                                              [("PRD-005", 150, "7200.00"), ("PRD-009", 40, "9400.00")], fe)),
            (f(66), lambda fe: self.oc_recibir("oc_recibida", {"PRD-005": 150, "PRD-009": 40}, fe)),
            (f(40), lambda fe: self.oc_crear("oc_cancelada", NIT_PAPEL, 0, [("PRD-008", 100, "4300.00")], fe)),
            (f(39), lambda fe: self.oc_cancelar("oc_cancelada")),
            (f(30), lambda fe: self.traslado(0, 1, "PRD-002", 120, fe)),
            (f(25), lambda fe: self.oc_crear("oc_parcial", NIT_ANDINA, 0,
                                              [("PRD-006", 300, "3300.00"), ("PRD-003", 200, "4100.00")], fe)),
            (f(20), lambda fe: self.oc_recibir("oc_parcial", {"PRD-006": 120, "PRD-003": 200}, fe)),
            (f(15), lambda fe: self.devolucion({
                "tipo": "CLIENTE", "bodega_id": self.bid[1], "referencia_cliente": "FAC-10234",
                "motivo": "Error de despacho y empaque dañado",
                "detalle": [{"producto_id": self.pid["PRD-003"], "cantidad": "6", "condicion": "APTO"},
                            {"producto_id": self.pid["PRD-003"], "cantidad": "2", "condicion": "AVERIADO"}]}, fe)),
            (f(12), lambda fe: self.traslado(0, 2, "PRD-003", 80, fe)),
            (f(10), lambda fe: self.devolucion({
                "tipo": "PROVEEDOR", "bodega_id": self.bid[0], "proveedor_id": self.prov[NIT_ASEO],
                "motivo": "Lote con empaque defectuoso",
                "detalle": [{"producto_id": self.pid["PRD-005"], "cantidad": "5", "condicion": "AVERIADO"}]}, fe)),
            (f(8), lambda fe: self.salir(("PRD-009", 1), 2, fe, tipo="AJUSTE_SALIDA",
                                         motivo="Merma por daño en almacenamiento")),
            (f(3), lambda fe: self.oc_crear("oc_pendiente", NIT_LACTEOS, 0, [("PRD-001", 400, "3100.00")], fe)),
        ]

    # ------------------------------------------------------------------ resolución de ids

    def resolver_ids(self):
        base = settings.CATALOGO_SERVICE_URL.rstrip("/")
        self.pid = {}
        for codigo in PERFIL:
            r = requests.get(f"{base}/productos", params={"codigo": codigo}, timeout=10)
            resultados = r.json().get("results", []) if r.status_code == 200 else []
            if not resultados:
                raise CommandError(f"El producto {codigo} no existe en catálogo. Ejecute antes seed_catalogo.")
            self.pid[codigo] = resultados[0]["id"]
        self.prov = {}
        for nit in (NIT_ANDINA, NIT_LACTEOS, NIT_ASEO, NIT_PAPEL):
            r = requests.get(f"{base}/proveedores", params={"nit": nit}, timeout=10)
            datos = r.json() if r.status_code == 200 else []
            if not datos:
                raise CommandError(f"El proveedor {nit} no existe en catálogo. Ejecute antes seed_catalogo.")
            self.prov[nit] = datos[0]["id"]

    # ------------------------------------------------------------------ ejecución

    def handle(self, *args, **opciones):
        hoy = timezone.localdate()
        self.hasta = date.fromisoformat(opciones["hasta"]) if opciones["hasta"] else hoy - timedelta(days=1)
        if self.hasta >= hoy:
            raise CommandError("--hasta debe ser anterior a hoy")
        self.series = [(codigo, idx) for idx in range(3) for codigo in PERFIL]
        if not opciones["confirmo"]:
            self.stdout.write(
                f"[dry-run] Crearía {len(BODEGAS)} bodegas, {len(self.series)} registros de stock, ~2.000 salidas y sus "
                f"reposiciones entre {self.hasta - timedelta(days=363)} y {self.hasta}, 4 órdenes de compra, "
                "2 traslados, 2 devoluciones y 1 ajuste, con 6 series en quiebre y 6 en sobrestock.\n"
                "Ejecute con --confirmo para aplicarlo.")
            return
        if Movimiento.objects.exists():
            if opciones["solo_si_vacio"]:
                self.stdout.write("Existencias ya tiene datos: no se siembra nada.")
                return
            raise CommandError("Ya existen movimientos en existencias; el kardex no se puede borrar. "
                               "Para volver a sembrar recree el volumen de la base de existencias.")

        self.api = Api()
        self.stock, self.demanda, self.docs = {}, {s: 0 for s in self.series}, {}
        self.lotes_usados, self.n_movimientos, self.n_docs = set(), 0, 0
        rng = random.Random(opciones["semilla"])

        self.stdout.write("Resolviendo productos y proveedores en catálogo...")
        self.resolver_ids()

        self.stdout.write("Creando bodegas y registrando stock...")
        existentes = {b["codigo"]: b["id"] for b in self.api.get("/bodegas")}
        self.bid = {}
        for idx, (codigo, nombre, region, ciudad, _) in enumerate(BODEGAS):
            self.bid[idx] = existentes.get(codigo) or self.api.post("/bodegas", {
                "codigo": codigo, "nombre": nombre, "region": region, "ciudad": ciudad}).json()["id"]
        self.clave_inversa = {(self.pid[c], self.bid[i]): (c, i) for c, i in self.series}
        self.exist_id = {}
        for serie in self.series:
            codigo, idx = serie
            self.exist_id[serie] = self.api.post("/stock", {
                "producto_id": self.pid[codigo], "bodega_id": self.bid[idx], "stock_minimo": "0"}).json()["id"]
            self.stock[serie] = Decimal(0)

        eventos = self.generar_eventos(rng)
        eventos += [(fecha, "doc", None, accion) for fecha, accion in self.documentos(self.hasta)]
        eventos.sort(key=lambda e: e[0])
        self.stdout.write(f"Simulando {len(eventos)} eventos (esto toma unos minutos)...")
        t0 = time.time()
        for i, (fecha, tipo, serie, dato) in enumerate(eventos, 1):
            if tipo == "salida":
                self.evento_salida(serie, dato, fecha)
            else:
                dato(fecha)
            if i % 250 == 0:
                self.stdout.write(f"  {i}/{len(eventos)} eventos ({time.time() - t0:.0f}s)")

        self.stdout.write("Ajustando el estado final (quiebre / óptimo / sobrestock)...")
        self.sync()
        fin = con_hora(self.hasta, 18)
        mensual = {s: max(1, self.demanda[s] / 3) for s in self.series}
        for serie in self.series:
            m, actual = Decimal(str(mensual[serie])), self.stock[serie]
            if serie in QUIEBRE:
                objetivo = max(Decimal(3), (m * Decimal("0.15")).quantize(Decimal(1)))
            elif serie in SOBRESTOCK:
                objetivo = (m * Decimal("3.6")).quantize(Decimal(1))
            else:
                objetivo = (m * Decimal("1.1")).quantize(Decimal(1))
                if Decimal("0.9") * m <= actual <= Decimal("1.4") * m:
                    continue
            if actual > objetivo:
                self.salir(serie, int(actual - objetivo), fin, tipo="AJUSTE_SALIDA",
                           motivo="Ajuste por conteo físico de inventario")
            elif actual < objetivo:
                self.entrar(serie, int(objetivo - actual), fin,
                            motivo="Compra por volumen" if serie in SOBRESTOCK else "Reposición programada")

        self.stdout.write("Agregando lotes de demostración (próximos a vencer y vencido)...")
        self.entrar(("PRD-001", 0), 10, fin, motivo="Lote próximo a vencer",
                    vida=(hoy - self.hasta).days + 4, numero="DEMO-PV-001")
        self.entrar(("PRD-004", 0), 10, fin, motivo="Lote próximo a vencer",
                    vida=(hoy - self.hasta).days + 5, numero="DEMO-PV-004")
        self.entrar(("PRD-010", 2), 8, fin, motivo="Lote vencido sin rotar",
                    vida=-((hoy - self.hasta).days + 10), numero="DEMO-VENC-010")

        self.stdout.write("Configurando umbrales...")
        for serie in self.series:
            m = mensual[serie]
            minimo = max(1, round(0.25 * m))
            self.api.put(f"/stock/{self.exist_id[serie]}/umbral",
                         {"stock_minimo": str(minimo), "stock_maximo": str(max(minimo + 1, round(2.0 * m)))})

        self.stdout.write("Provocando una alerta real de stock bajo (PRD-005 en bodega principal)...")
        self._mov(("PRD-005", 0), "SALIDA", 1, timezone.now(), "Venta que deja el stock bajo el mínimo")
        time.sleep(3)  # el envío de la alerta es asíncrono

        self.verificar(mensual)

    # ------------------------------------------------------------------ verificación

    def verificar(self, mensual):
        self.stdout.write("\nVerificación:")
        tipos_entrada = Movimiento.TIPOS_ENTRADA
        incoherentes = negativas = 0
        clases = {"quiebre": 0, "óptimo": 0, "sobrestock": 0}
        for e in Existencia.objects.all():
            suma = Decimal(0)
            for tipo, cant in Movimiento.objects.filter(producto_id=e.producto_id, bodega_id=e.bodega_id) \
                    .values_list("tipo", "cantidad"):
                suma += cant if tipo in tipos_entrada else -cant
            if suma != e.cantidad:
                incoherentes += 1
            if e.cantidad < 0:
                negativas += 1
            codigo, idx = self.clave_inversa[(e.producto_id, e.bodega_id)]
            m = Decimal(str(mensual[(codigo, idx)]))
            clases["quiebre" if e.cantidad < m * Decimal("0.5")
                   else "sobrestock" if e.cantidad > m * Decimal("1.8") else "óptimo"] += 1
        self.stdout.write(f"  Series: {Existencia.objects.count()} | movimientos: {Movimiento.objects.count()} "
                          f"| documentos: {self.n_docs}")
        self.stdout.write(f"  Saldos que no cuadran con el kardex: {incoherentes} | saldos negativos: {negativas}")
        self.stdout.write(f"  Series por nivel de stock (estimado): {clases}")
        self.stdout.write(f"  Bajo el mínimo ahora: {Existencia.objects.filter(cantidad__lt=F('stock_minimo')).count()}")
        estilo = self.style.SUCCESS if not incoherentes and not negativas else self.style.ERROR
        self.stdout.write(estilo("Siembra de existencias terminada."))
        self.stdout.write("Ids de bodega: " + ", ".join(f"{BODEGAS[i][0]}={self.bid[i]}" for i in range(3)))
