"""Lotes: vencimiento de perecederos. La cantidad solo cambia por movimientos (RF10)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import Lote
from ..serializers import LoteCorreccionSerializer, LoteSerializer
from ..utils import obtener_o_404, param_bool, param_fecha, param_int

CAMPOS_EDITABLES = {"numero_lote", "fecha_vencimiento"}


class LotesView(APIView):
    def get(self, request):
        qp = request.query_params
        qs = Lote.objects.order_by("fecha_vencimiento", "id")
        for campo in ("producto_id", "bodega_id"):
            valor = param_int(qp, campo)
            if valor is not None:
                qs = qs.filter(**{campo: valor})
        vence = param_fecha(qp, "vence_antes_de")
        if vence:
            qs = qs.filter(fecha_vencimiento__lte=vence)  # hasta esa fecha, inclusive
        if param_bool(qp, "con_saldo", defecto=True):
            qs = qs.filter(cantidad__gt=0)
        return Response(LoteSerializer(qs, many=True).data)


class LoteDetalleView(APIView):
    def patch(self, request, pk):
        """Corrige número de lote o fecha de vencimiento. No permite modificar la cantidad."""
        exigir_rol(request, ADMIN)
        lote = obtener_o_404(Lote, pk, "El lote")

        enviados = set(request.data.keys()) if hasattr(request.data, "keys") else set()
        if "cantidad" in enviados:
            raise ErrorNegocio(400, "CAMPO_NO_EDITABLE", "La cantidad de un lote solo puede cambiar mediante movimientos")
        extras = enviados - CAMPOS_EDITABLES
        if extras:
            raise ErrorNegocio(400, "CAMPO_NO_EDITABLE", f"Campos no editables: {', '.join(sorted(extras))}")
        if not enviados:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", "Envíe numero_lote o fecha_vencimiento")

        s = LoteCorreccionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        numero = d.get("numero_lote")
        if numero and Lote.objects.filter(producto_id=lote.producto_id, bodega_id=lote.bodega_id,
                                          numero_lote=numero).exclude(pk=lote.pk).exists():
            raise ErrorNegocio(400, "DATOS_INVALIDOS", f"Ya existe el lote {numero} para ese producto en la bodega")

        for campo, valor in d.items():
            setattr(lote, campo, valor)
        lote.save(update_fields=list(d.keys()))
        return Response(LoteSerializer(lote).data)
