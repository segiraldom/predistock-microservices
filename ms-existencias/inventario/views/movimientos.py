"""Movimientos manuales y kardex (RF04, RF10), e histórico para ms-analitica."""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import servicios
from ..identidad import ADMIN, OPERADOR_BODEGA, exigir_rol
from ..models import Movimiento
from ..serializers import MovimientoInputSerializer, MovimientoSerializer
from ..utils import paginar, param_fecha, param_int, param_opcion

TIPOS = set(Movimiento.Tipo.values)


def _rango_fechas(qs, query_params):
    """Filtra por desde/hasta (fechas locales, ambos inclusive)."""
    tz = timezone.get_current_timezone()
    desde = param_fecha(query_params, "desde")
    hasta = param_fecha(query_params, "hasta")
    if desde:
        qs = qs.filter(fecha__gte=datetime.combine(desde, time.min, tzinfo=tz))
    if hasta:
        qs = qs.filter(fecha__lt=datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=tz))
    return qs, desde, hasta


class MovimientosView(APIView):
    def get(self, request):
        """Kardex: quién, cuándo y qué movimiento se realizó, del más reciente al más antiguo."""
        qp = request.query_params
        qs = Movimiento.objects.order_by("-fecha", "-id")
        for campo in ("producto_id", "bodega_id", "usuario_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        tipo = param_opcion(qp, "tipo", TIPOS)
        if tipo:
            qs = qs.filter(tipo=tipo)
        qs, _, _ = _rango_fechas(qs, qp)

        items, total = paginar(qs, qp)
        resp = Response(MovimientoSerializer(items, many=True).data)
        resp["X-Total-Count"] = str(total)
        return resp

    def post(self, request):
        """Entrada, salida o ajuste manual en una sola transacción (valida saldo, inserta y actualiza)."""
        identidad = exigir_rol(request, ADMIN, OPERADOR_BODEGA)
        s = MovimientoInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        bodega = servicios.bodega_operable(identidad, d["bodega_id"])

        with transaction.atomic():
            movimientos = servicios.registrar_movimiento(
                producto_id=d["producto_id"], bodega=bodega, tipo=d["tipo"], cantidad=d["cantidad"],
                usuario_id=identidad.usuario_id, motivo=d.get("motivo") or None,
                lote_id=d.get("lote_id"), numero_lote=d.get("numero_lote"),
                fecha_vencimiento=d.get("fecha_vencimiento"),
            )

        # Si una salida consumió varios lotes se generan varios movimientos: se devuelve el último
        # (el que tiene el saldo final) y los ids de todos van en la cabecera.
        resp = Response(MovimientoSerializer(movimientos[-1]).data, status=201)
        resp["X-Movimientos-Ids"] = ",".join(str(m.id) for m in movimientos)
        return resp


class HistoricoView(APIView):
    """
    Histórico consolidado para el pipeline de ms-analitica (collector.py).

    Formato {"data": [...]} y tipo SALIDA expuesto como SALIDA_VENTA, que es lo que
    espera el preprocesador de analítica. Por defecto, los últimos 365 días.
    """
    MAPEO_TIPOS = {"SALIDA": "SALIDA_VENTA"}

    def get(self, request):
        qp = request.query_params
        qs = Movimiento.objects.order_by("fecha", "id")
        for campo in ("producto_id", "bodega_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        qs, desde, _ = _rango_fechas(qs, qp)
        if desde is None:
            qs = qs.filter(fecha__gte=timezone.now() - timedelta(days=365))

        data = [
            {
                "id": m["id"],
                "producto_id": m["producto_id"],
                "bodega_id": m["bodega_id"],
                "tipo": self.MAPEO_TIPOS.get(m["tipo"], m["tipo"]),
                "cantidad": float(m["cantidad"]),
                "fecha": timezone.localtime(m["fecha"]).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for m in qs.values("id", "producto_id", "bodega_id", "tipo", "cantidad", "fecha").iterator()
        ]
        return Response({"data": data, "total": len(data)})
