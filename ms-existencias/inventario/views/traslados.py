"""Traslados entre bodegas (RF04). Cada producto genera TRASLADO_SALIDA en origen y TRASLADO_ENTRADA en destino."""
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import catalogo, servicios
from ..identidad import ADMIN, OPERADOR_BODEGA, exigir_rol
from ..models import DetalleTraslado, Traslado
from ..serializers import TrasladoInputSerializer, TrasladoSerializer
from ..utils import obtener_o_404, param_fecha, param_int


class TrasladosView(APIView):
    def get(self, request):
        qp = request.query_params
        qs = Traslado.objects.prefetch_related("detalle").order_by("-fecha", "-id")
        for campo in ("bodega_origen_id", "bodega_destino_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        desde, hasta = param_fecha(qp, "desde"), param_fecha(qp, "hasta")
        if desde:
            qs = qs.filter(fecha__date__gte=desde)
        if hasta:
            qs = qs.filter(fecha__date__lte=hasta)
        return Response(TrasladoSerializer(qs, many=True).data)

    def post(self, request):
        identidad = exigir_rol(request, ADMIN, OPERADOR_BODEGA)
        s = TrasladoInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        # El operador solo despacha desde su bodega; el destino puede ser cualquier bodega activa
        origen = servicios.bodega_operable(identidad, d["bodega_origen_id"])
        destino = servicios.bodega_operable(identidad, d["bodega_destino_id"], restringir_operador=False)
        perecederos = {l["producto_id"]: catalogo.es_perecedero(l["producto_id"]) for l in d["detalle"]}

        with transaction.atomic():
            traslado = Traslado.objects.create(bodega_origen=origen, bodega_destino=destino,
                                               sugerencia_id=d.get("sugerencia_id"),
                                               usuario_id=identidad.usuario_id)
            for linea in d["detalle"]:
                pid, cantidad = linea["producto_id"], linea["cantidad"]
                DetalleTraslado.objects.create(traslado=traslado, producto_id=pid, cantidad=cantidad)
                comunes = {"producto_id": pid, "usuario_id": identidad.usuario_id,
                           "traslado": traslado, "perecedero": perecederos[pid]}
                salidas = servicios.registrar_movimiento(
                    bodega=origen, tipo="TRASLADO_SALIDA", cantidad=cantidad, **comunes)
                # El lote viaja con la mercancía: misma numeración y vencimiento en la bodega destino
                for salida in salidas:
                    lote = salida.lote
                    servicios.registrar_movimiento(
                        bodega=destino, tipo="TRASLADO_ENTRADA", cantidad=salida.cantidad,
                        numero_lote=lote.numero_lote if lote else None,
                        fecha_vencimiento=lote.fecha_vencimiento if lote else None,
                        crear_existencia=True, **comunes)

        return Response(TrasladoSerializer(traslado).data, status=201)


class TrasladoDetalleView(APIView):
    def get(self, request, pk):
        return Response(TrasladoSerializer(obtener_o_404(Traslado, pk, "El traslado")).data)

