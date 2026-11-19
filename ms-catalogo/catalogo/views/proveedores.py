"""Proveedores (RF03)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..identidad import ADMIN, exigir_rol
from ..models import Proveedor
from ..serializers import ProveedorSerializer
from ..utils import guardar_o_409, obtener_o_404, param_bool, verificar_unico


class ProveedorListaView(APIView):
    def get(self, request):
        qs = Proveedor.objects.order_by("id")
        razon_social = request.query_params.get("razon_social")
        if razon_social:
            qs = qs.filter(razon_social__icontains=razon_social)
        nit = request.query_params.get("nit")
        if nit:
            qs = qs.filter(nit=nit)
        qs = qs.filter(activo=param_bool(request.query_params, "activo", defecto=True))
        return Response(ProveedorSerializer(qs, many=True).data)

    def post(self, request):
        exigir_rol(request, ADMIN)
        s = ProveedorSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        verificar_unico(Proveedor, "nit", s.validated_data["nit"], "un proveedor")
        with guardar_o_409("Ya existe un proveedor con ese NIT"):
            proveedor = s.save()
        return Response(ProveedorSerializer(proveedor).data, status=201)


class ProveedorDetalleView(APIView):
    def get(self, request, pk):
        # Incluye proveedores inactivos: ms-existencias necesita ver `activo` para rechazarlos él mismo.
        return Response(ProveedorSerializer(obtener_o_404(Proveedor, pk, "El proveedor")).data)

    def put(self, request, pk):
        exigir_rol(request, ADMIN)
        proveedor = obtener_o_404(Proveedor, pk, "El proveedor")
        s = ProveedorSerializer(proveedor, data=request.data)
        s.is_valid(raise_exception=True)
        verificar_unico(Proveedor, "nit", s.validated_data["nit"], "un proveedor", excluir_id=proveedor.pk)
        with guardar_o_409("Ya existe un proveedor con ese NIT"):
            proveedor = s.save()
        return Response(ProveedorSerializer(proveedor).data)

    def delete(self, request, pk):
        exigir_rol(request, ADMIN)
        proveedor = obtener_o_404(Proveedor, pk, "El proveedor")
        proveedor.activo = False
        proveedor.save(update_fields=["activo"])
        return Response(status=204)
