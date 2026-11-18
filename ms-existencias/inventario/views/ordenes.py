"""
Órdenes de compra (RF06). Estados: PENDIENTE -> PARCIAL -> RECIBIDA, o CANCELADA.
Crear una orden no mueve stock; cada recepción genera movimientos ENTRADA.
"""
import uuid

from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import catalogo, servicios
from ..errores import ErrorNegocio
from ..identidad import ADMIN, OPERADOR_BODEGA, exigir_rol
from ..models import DetalleOrdenCompra, OrdenCompra
from ..serializers import (EstadoOrdenInputSerializer, OrdenCompraInputSerializer,
                           OrdenCompraSerializer, RecepcionInputSerializer)
from ..utils import obtener_o_404, param_int, param_opcion

Estado = OrdenCompra.Estado


def _respuesta(orden, status=200):
    orden = OrdenCompra.objects.prefetch_related("detalle").get(pk=orden.pk)
    return Response(OrdenCompraSerializer(orden).data, status=status)


class OrdenesView(APIView):
    def get(self, request):
        qp = request.query_params
        qs = OrdenCompra.objects.prefetch_related("detalle").order_by("-fecha_emision", "-id")
        estado = param_opcion(qp, "estado", set(Estado.values))
        if estado:
            qs = qs.filter(estado=estado)
        for campo in ("proveedor_id", "bodega_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        return Response(OrdenCompraSerializer(qs, many=True).data)

    def post(self, request):
        identidad = exigir_rol(request, ADMIN)
        s = OrdenCompraInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        bodega = servicios.bodega_operable(identidad, d["bodega_id"])

        # Validaciones contra catálogo antes de abrir la transacción (422 / 503)
        catalogo.obtener_proveedor(d["proveedor_id"])
        for linea in d["detalle"]:
            catalogo.obtener_producto(linea["producto_id"])

        with transaction.atomic():
            orden = OrdenCompra.objects.create(numero=uuid.uuid4().hex[:20], proveedor_id=d["proveedor_id"],
                                               bodega=bodega, creada_por=identidad.usuario_id)
            orden.numero = f"OC-{orden.fecha_emision.year}-{orden.pk:04d}"
            orden.save(update_fields=["numero"])
            DetalleOrdenCompra.objects.bulk_create(
                DetalleOrdenCompra(orden_compra=orden, **linea) for linea in d["detalle"])
        return _respuesta(orden, status=201)


class OrdenDetalleView(APIView):
    def get(self, request, pk):
        return _respuesta(obtener_o_404(OrdenCompra, pk, "La orden de compra"))


class OrdenEstadoView(APIView):
    def patch(self, request, pk):
        """Uso principal: cancelar. PARCIAL y RECIBIDA se asignan solas al recibir mercancía."""
        exigir_rol(request, ADMIN)
        EstadoOrdenInputSerializer(data=request.data).is_valid(raise_exception=True)
        with transaction.atomic():
            orden = OrdenCompra.objects.select_for_update().filter(pk=pk).first()
            if orden is None:
                raise ErrorNegocio(404, "NO_ENCONTRADO", f"La orden de compra {pk} no existe")
            if orden.estado != Estado.PENDIENTE:
                raise ErrorNegocio(409, "ESTADO_INVALIDO",
                                   f"La orden {orden.numero} está {orden.estado} y no puede cancelarse")
            orden.estado = Estado.CANCELADA
            orden.save(update_fields=["estado"])
        return _respuesta(orden)


class RecepcionesView(APIView):
    def post(self, request, pk):
        """Por cada línea: movimiento ENTRADA, suma al stock, crea el lote si aplica y acumula lo recibido."""
        identidad = exigir_rol(request, ADMIN, OPERADOR_BODEGA)
        s = RecepcionInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        lineas = s.validated_data["lineas"]

        with transaction.atomic():
            orden = OrdenCompra.objects.select_for_update().filter(pk=pk).first()
            if orden is None:
                raise ErrorNegocio(404, "NO_ENCONTRADO", f"La orden de compra {pk} no existe")
            if orden.estado in (Estado.CANCELADA, Estado.RECIBIDA):
                raise ErrorNegocio(409, "ESTADO_INVALIDO", f"La orden {orden.numero} está {orden.estado}")
            bodega = servicios.bodega_operable(identidad, orden.bodega_id)
            detalle = {l.pk: l for l in orden.detalle.select_for_update()}

            for linea in lineas:
                item = detalle.get(linea["detalle_id"])
                if item is None:
                    raise ErrorNegocio(400, "DATOS_INVALIDOS",
                                       f"La línea {linea['detalle_id']} no pertenece a la orden {orden.numero}")
                pendiente = item.cantidad_solicitada - item.cantidad_recibida
                if linea["cantidad"] > pendiente:
                    raise ErrorNegocio(400, "CANTIDAD_EXCEDIDA",
                                       f"Línea {item.pk}: pendiente {servicios.texto(pendiente)}, "
                                       f"recibido {servicios.texto(linea['cantidad'])}")
                servicios.registrar_movimiento(
                    producto_id=item.producto_id, bodega=bodega, tipo="ENTRADA", cantidad=linea["cantidad"],
                    usuario_id=identidad.usuario_id, numero_lote=linea.get("numero_lote"),
                    fecha_vencimiento=linea.get("fecha_vencimiento"), orden_compra=orden,
                    crear_existencia=True, motivo=f"Recepción {orden.numero}")
                item.cantidad_recibida += linea["cantidad"]
                item.save(update_fields=["cantidad_recibida"])

            completa = all(l.cantidad_recibida >= l.cantidad_solicitada for l in detalle.values())
            orden.estado = Estado.RECIBIDA if completa else Estado.PARCIAL
            orden.save(update_fields=["estado"])

        return _respuesta(orden, status=201)
