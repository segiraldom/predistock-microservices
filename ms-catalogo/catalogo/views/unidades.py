"""Unidades de medida (RF01)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import UnidadMedida
from ..serializers import UnidadMedidaSerializer
from ..utils import guardar_o_409, obtener_o_404, verificar_unico


class UnidadListaView(APIView):
    def get(self, request):
        return Response(UnidadMedidaSerializer(UnidadMedida.objects.order_by("id"), many=True).data)

    def post(self, request):
        exigir_rol(request, ADMIN)
        s = UnidadMedidaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        verificar_unico(UnidadMedida, "codigo", s.validated_data["codigo"], "una unidad de medida")
        with guardar_o_409("Ya existe una unidad de medida con ese código"):
            unidad = s.save()
        return Response(UnidadMedidaSerializer(unidad).data, status=201)


class UnidadDetalleView(APIView):
    def put(self, request, pk):
        exigir_rol(request, ADMIN)
        unidad = obtener_o_404(UnidadMedida, pk, "La unidad de medida")
        s = UnidadMedidaSerializer(unidad, data=request.data)
        s.is_valid(raise_exception=True)
        verificar_unico(UnidadMedida, "codigo", s.validated_data["codigo"], "una unidad de medida",
                        excluir_id=unidad.pk)
        with guardar_o_409("Ya existe una unidad de medida con ese código"):
            unidad = s.save()
        return Response(UnidadMedidaSerializer(unidad).data)

    def delete(self, request, pk):
        exigir_rol(request, ADMIN)
        unidad = obtener_o_404(UnidadMedida, pk, "La unidad de medida")
        en_uso = unidad.productos.count()
        if en_uso:
            raise ErrorNegocio(409, "UNIDAD_EN_USO",
                               f"La unidad {unidad.codigo} está asignada a {en_uso} "
                               f"{'producto' if en_uso == 1 else 'productos'} y no puede eliminarse")
        unidad.delete()
        return Response(status=204)
