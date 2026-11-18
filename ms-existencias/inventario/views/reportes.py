"""Reportes básicos de inventario (RF11): existencias actuales, valorización y rotación."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import catalogo
from ..errores import ErrorNegocio
from ..models import Existencia, Movimiento
from ..utils import param_fecha, param_int, param_opcion

ESTADOS = {
    "BAJO_MINIMO": Q(cantidad__lt=F("stock_minimo")),
    "SOBRESTOCK": Q(stock_maximo__isnull=False, cantidad__gt=F("stock_maximo")),
}
ESTADOS["NORMAL"] = ~ESTADOS["BAJO_MINIMO"] & ~ESTADOS["SOBRESTOCK"]


def _estado(e):
    if e.cantidad < e.stock_minimo:
        return "BAJO_MINIMO"
    if e.stock_maximo is not None and e.cantidad > e.stock_maximo:
        return "SOBRESTOCK"
    return "NORMAL"


def _fecha_corte():
    return timezone.localtime().isoformat(timespec="seconds")


class ReporteExistenciasView(APIView):
    """Saldo actual de cada producto por bodega y su estado frente a los umbrales."""

    def get(self, request):
        qp = request.query_params
        qs = Existencia.objects.select_related("bodega").order_by("bodega_id", "producto_id")
        bodega_id = param_int(qp, "bodega_id")
        if bodega_id is not None:
            qs = qs.filter(bodega_id=bodega_id)
        estado = param_opcion(qp, "estado", set(ESTADOS))
        if estado:
            qs = qs.filter(ESTADOS[estado])

        filas = list(qs)
        productos = catalogo.datos_productos({e.producto_id for e in filas})  # nombres y códigos, si hay catálogo
        items = [{
            "producto_id": e.producto_id,
            "producto_codigo": productos.get(e.producto_id, {}).get("codigo"),
            "producto_nombre": productos.get(e.producto_id, {}).get("nombre"),
            "bodega_id": e.bodega_id,
            "bodega_nombre": e.bodega.nombre,
            "cantidad": float(e.cantidad),
            "stock_minimo": float(e.stock_minimo),
            "stock_maximo": float(e.stock_maximo) if e.stock_maximo is not None else None,
            "estado": _estado(e),
        } for e in filas]
        return Response({"fecha_corte": _fecha_corte(), "total_registros": len(items), "items": items})


class ReporteValorizacionView(APIView):
    """Valor del inventario = cantidad en existencias x costo del producto (costo tomado de catálogo)."""

    def get(self, request):
        qs = Existencia.objects.select_related("bodega").filter(cantidad__gt=0).order_by("bodega_id")
        bodega_id = param_int(request.query_params, "bodega_id")
        if bodega_id is not None:
            qs = qs.filter(bodega_id=bodega_id)

        filas = list(qs)
        costos = catalogo.costos_productos({e.producto_id for e in filas})  # 503 si catálogo no responde

        por_bodega = {}
        for e in filas:
            b = por_bodega.setdefault(e.bodega_id, {"bodega_id": e.bodega_id, "bodega_nombre": e.bodega.nombre,
                                                    "total_productos": 0, "valor": Decimal("0")})
            b["total_productos"] += 1
            b["valor"] += e.cantidad * costos[e.producto_id]

        bodegas = list(por_bodega.values())
        total = sum((b["valor"] for b in bodegas), Decimal("0"))
        for b in bodegas:
            b["valor"] = float(round(b["valor"], 2))
        return Response({"fecha_corte": _fecha_corte(), "valor_total": float(round(total, 2)), "por_bodega": bodegas})


class ReporteRotacionView(APIView):
    """
    Rotación por producto en un periodo, a partir del kardex:
      unidades_salida = suma de movimientos SALIDA del periodo
      stock_promedio  = (saldo al inicio + saldo al final) / 2, reconstruidos desde el kardex
      indice_rotacion = unidades_salida / stock_promedio
    Incluye productos sin salidas, para que aparezcan en el reporte de MENOR rotación.
    """

    def get(self, request):
        qp = request.query_params
        desde = param_fecha(qp, "desde", obligatorio=True)
        hasta = param_fecha(qp, "hasta", obligatorio=True)
        if desde > hasta:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", "'desde' no puede ser posterior a 'hasta'")
        bodega_id = param_int(qp, "bodega_id")
        orden = param_opcion(qp, "orden", {"MAYOR", "MENOR"}) or "MAYOR"
        limite = param_int(qp, "limite", 10, minimo=1, maximo=100)

        tz = timezone.get_current_timezone()
        inicio = datetime.combine(desde, time.min, tzinfo=tz)
        fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=tz)

        def saldo_antes_de(momento):
            return Subquery(
                Movimiento.objects.filter(producto_id=OuterRef("producto_id"), bodega_id=OuterRef("bodega_id"),
                                          fecha__lt=momento)
                .order_by("-fecha", "-id").values("saldo_resultante")[:1],
                output_field=DecimalField(max_digits=14, decimal_places=3))

        existencias = Existencia.objects.all()
        salidas = Movimiento.objects.filter(tipo="SALIDA", fecha__gte=inicio, fecha__lt=fin)
        if bodega_id is not None:
            existencias = existencias.filter(bodega_id=bodega_id)
            salidas = salidas.filter(bodega_id=bodega_id)

        saldos = defaultdict(lambda: [Decimal("0"), Decimal("0")])  # producto -> [inicial, final]
        for fila in existencias.annotate(ini=saldo_antes_de(inicio), fin=saldo_antes_de(fin)) \
                               .values("producto_id", "ini", "fin"):
            saldos[fila["producto_id"]][0] += fila["ini"] or 0
            saldos[fila["producto_id"]][1] += fila["fin"] or 0
        unidades = {f["producto_id"]: f["total"]
                    for f in salidas.values("producto_id").annotate(total=Sum("cantidad"))}

        filas = []
        for pid in set(saldos) | set(unidades):
            vendidas = unidades.get(pid, Decimal("0"))
            promedio = sum(saldos[pid]) / 2
            indice = (vendidas / promedio) if promedio > 0 else None
            filas.append((pid, vendidas, promedio, indice))

        def clave(f):
            _, vendidas, _, indice = f
            # Sin stock promedio pero con ventas: todo lo que entró salió (rotación máxima)
            valor = indice if indice is not None else (Decimal("Infinity") if vendidas > 0 else Decimal("0"))
            return (valor, vendidas)

        filas.sort(key=clave, reverse=(orden == "MAYOR"))
        filas = filas[:limite]
        nombres = catalogo.nombres_productos({f[0] for f in filas})
        items = [{
            "producto_id": pid,
            "producto_nombre": nombres.get(pid),
            "unidades_salida": float(vendidas),
            "stock_promedio": float(round(promedio, 3)),
            "indice_rotacion": float(round(indice, 2)) if indice is not None else None,
        } for pid, vendidas, promedio, indice in filas]
        return Response({"desde": desde.isoformat(), "hasta": hasta.isoformat(), "orden": orden, "items": items})
