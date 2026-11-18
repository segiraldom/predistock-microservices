"""
Devoluciones (RF13).
- CLIENTE: las líneas APTO vuelven al stock (DEVOLUCION_CLIENTE); las AVERIADO solo quedan registradas.
- PROVEEDOR: cada línea resta del stock (DEVOLUCION_PROVEEDOR); el proveedor se valida con catálogo.
"""
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import catalogo, servicios
from ..identidad import ADMIN, OPERADOR_BODEGA, exigir_rol
from ..models import DetalleDevolucion, Devolucion
from ..serializers import DevolucionInputSerializer, DevolucionSerializer
from ..utils import obtener_o_404, param_int, param_opcion


class DevolucionesView(APIView):
    def get(self, request):
        qp = request.query_params
        qs = Devolucion.objects.prefetch_related("detalle").order_by("-fecha", "-id")
        tipo = param_opcion(qp, "tipo", set(Devolucion.Tipo.values))
        if tipo:
            qs = qs.filter(tipo=tipo)
        for campo in ("bodega_id", "proveedor_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        return Response(DevolucionSerializer(qs, many=True).data)

    def post(self, request):
        identidad = exigir_rol(request, ADMIN, OPERADOR_BODEGA)
        s = DevolucionInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        bodega = servicios.bodega_operable(identidad, d["bodega_id"])
        es_cliente = d["tipo"] == Devolucion.Tipo.CLIENTE
        if not es_cliente:
            catalogo.obtener_proveedor(d["proveedor_id"])  # 422 / 503 antes de abrir la transacción

        with transaction.atomic():
            devolucion = Devolucion.objects.create(
                tipo=d["tipo"], bodega=bodega, proveedor_id=d["proveedor_id"],
                referencia_cliente=d.get("referencia_cliente") or None, motivo=d["motivo"],
                usuario_id=identidad.usuario_id)
            for linea in d["detalle"]:
                DetalleDevolucion.objects.create(devolucion=devolucion, **linea)
                if es_cliente and linea["condicion"] == DetalleDevolucion.Condicion.AVERIADO:
                    continue  # se registra, pero no vuelve al stock
                servicios.registrar_movimiento(
                    producto_id=linea["producto_id"], bodega=bodega,
                    tipo="DEVOLUCION_CLIENTE" if es_cliente else "DEVOLUCION_PROVEEDOR",
                    cantidad=linea["cantidad"], usuario_id=identidad.usuario_id,
                    motivo=d["motivo"], devolucion=devolucion)

        return Response(DevolucionSerializer(devolucion).data, status=201)


class DevolucionDetalleView(APIView):
    def get(self, request, pk):
        return Response(DevolucionSerializer(obtener_o_404(Devolucion, pk, "La devolución")).data)
