"""Bodegas (RF05): ubicaciones físicas de almacenamiento."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import Bodega
from ..serializers import BodegaSerializer
from ..utils import obtener_o_404, param_bool


def _verificar_codigo_unico(codigo, excluir_id=None):
    qs = Bodega.objects.filter(codigo__iexact=codigo)
    if excluir_id is not None:
        qs = qs.exclude(pk=excluir_id)
    if qs.exists():
        raise ErrorNegocio(409, "CONFLICTO", f"Ya existe una bodega con el código {codigo}")


class BodegaListaView(APIView):
    def get(self, request):
        qs = Bodega.objects.order_by("id")
        region = request.query_params.get("region")
        if region:
            qs = qs.filter(region__iexact=region)
        qs = qs.filter(activa=param_bool(request.query_params, "activa", defecto=True))
        return Response(BodegaSerializer(qs, many=True).data)

    def post(self, request):
        exigir_rol(request, ADMIN)
        s = BodegaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        _verificar_codigo_unico(s.validated_data["codigo"])
        bodega = s.save()
        return Response(BodegaSerializer(bodega).data, status=201)


class BodegaDetalleView(APIView):
    def get(self, request, pk):
        return Response(BodegaSerializer(obtener_o_404(Bodega, pk, "La bodega")).data)

    def put(self, request, pk):
        exigir_rol(request, ADMIN)
        bodega = obtener_o_404(Bodega, pk, "La bodega")
        s = BodegaSerializer(bodega, data=request.data)
        s.is_valid(raise_exception=True)
        _verificar_codigo_unico(s.validated_data["codigo"], excluir_id=bodega.pk)
        return Response(BodegaSerializer(s.save()).data)
