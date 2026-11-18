"""
Stock (RF04, RF05, RF09): saldo por producto y bodega.

El saldo (cantidad) nunca se edita aquí: solo cambia mediante movimientos del kardex.
Estos endpoints registran el producto en la bodega y configuran sus umbrales.
"""
from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import catalogo
from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import Bodega, Existencia
from ..serializers import ExistenciaInputSerializer, ExistenciaSerializer, UmbralInputSerializer
from ..utils import obtener_o_404, paginar, param_bool, param_int


class StockView(APIView):
    def get(self, request):
        """Consulta más frecuente del sistema (RNF06): lee la tabla existencias sin recalcular el kardex."""
        qp = request.query_params
        qs = Existencia.objects.order_by("bodega_id", "producto_id")

        producto_id = param_int(qp, "producto_id")
        bodega_id = param_int(qp, "bodega_id")
        if producto_id is not None:
            qs = qs.filter(producto_id=producto_id)
        if bodega_id is not None:
            qs = qs.filter(bodega_id=bodega_id)
        if param_bool(qp, "bajo_minimo", defecto=False):
            qs = qs.filter(cantidad__lt=F("stock_minimo"))

        items, total = paginar(qs, qp)
        nombres = catalogo.nombres_productos({e.producto_id for e in items})
        resp = Response(ExistenciaSerializer(items, many=True, context={"nombres": nombres}).data)
        resp["X-Total-Count"] = str(total)
        return resp

    def post(self, request):
        """Registra un producto en una bodega con cantidad 0 y sus umbrales."""
        exigir_rol(request, ADMIN)
        s = ExistenciaInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        bodega = Bodega.objects.filter(pk=d["bodega_id"]).first()
        if bodega is None:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La bodega {d['bodega_id']} no existe")
        if not bodega.activa:
            raise ErrorNegocio(400, "BODEGA_INACTIVA", f"La bodega {bodega.pk} está inactiva")
        if Existencia.objects.filter(producto_id=d["producto_id"], bodega=bodega).exists():
            raise ErrorNegocio(409, "PRODUCTO_YA_REGISTRADO",
                               f"El producto {d['producto_id']} ya está registrado en la bodega {bodega.pk}")

        producto = catalogo.obtener_producto(d["producto_id"])  # 422 / 503 si no es válido

        try:
            with transaction.atomic():
                existencia = Existencia.objects.create(
                    producto_id=d["producto_id"], bodega=bodega, cantidad=0,
                    stock_minimo=d["stock_minimo"], stock_maximo=d.get("stock_maximo"),
                )
        except IntegrityError:  # otra petición lo registró al mismo tiempo
            raise ErrorNegocio(409, "PRODUCTO_YA_REGISTRADO",
                               f"El producto {d['producto_id']} ya está registrado en la bodega {bodega.pk}")

        nombres = {existencia.producto_id: producto.get("nombre")} if producto else {}
        return Response(ExistenciaSerializer(existencia, context={"nombres": nombres}).data, status=201)


class UmbralView(APIView):
    def put(self, request, pk):
        """Configura stock mínimo (umbral de alerta RF09) y máximo."""
        exigir_rol(request, ADMIN)
        existencia = obtener_o_404(Existencia, pk, "El registro de stock")
        s = UmbralInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        minimo = d["stock_minimo"]
        # Si no se envía stock_maximo se conserva; si se envía null se elimina.
        maximo = d["stock_maximo"] if "stock_maximo" in d else existencia.stock_maximo
        if maximo is not None and maximo < minimo:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", "stock_maximo debe ser mayor o igual que stock_minimo")

        existencia.stock_minimo = minimo
        existencia.stock_maximo = maximo
        # update_fields evita sobrescribir 'cantidad' con un valor leído antes de un movimiento concurrente
        existencia.save(update_fields=["stock_minimo", "stock_maximo"])
        existencia.refresh_from_db()
        nombres = catalogo.nombres_productos({existencia.producto_id})
        return Response(ExistenciaSerializer(existencia, context={"nombres": nombres}).data)
