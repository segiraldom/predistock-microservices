"""Productos (RF01, RF12) y su asociación con proveedores (RF03)."""
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import Categoria, Producto, ProductoProveedor, Proveedor, UnidadMedida
from ..serializers import (ProductoDetalleSerializer, ProductoInputSerializer, ProductoProveedorInputSerializer,
                           ProductoProveedorSerializer, ProductoProveedorUpdateSerializer, ProductoSerializer)
from ..utils import guardar_o_409, obtener_o_404, paginar, param_bool, param_int, verificar_unico
from .categorias import ids_con_descendientes


def _validar_referencias(datos, exigir_categoria_activa=True):
    """Categoría y unidad de medida deben existir; la categoría, además, estar activa
    (salvo que el producto vaya a quedar inactivo)."""
    categoria = Categoria.objects.filter(pk=datos["categoria_id"]).first()
    if categoria is None:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La categoría {datos['categoria_id']} no existe")
    if exigir_categoria_activa and not categoria.activo:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La categoría {datos['categoria_id']} está inactiva")
    unidad = UnidadMedida.objects.filter(pk=datos["unidad_medida_id"]).first()
    if unidad is None:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La unidad de medida {datos['unidad_medida_id']} no existe")
    return categoria, unidad


def _aplicar(producto, datos, categoria, unidad):
    producto.codigo = datos["codigo"]
    producto.nombre = datos["nombre"]
    producto.descripcion = datos.get("descripcion")
    producto.categoria = categoria
    producto.unidad_medida = unidad
    producto.precio_venta = datos["precio_venta"]
    producto.costo = datos["costo"]
    producto.es_perecedero = datos.get("es_perecedero", False)


class ProductoListaView(APIView):
    def get(self, request):
        params = request.query_params
        qs = Producto.objects.order_by("id")
        if params.get("nombre"):
            qs = qs.filter(nombre__icontains=params["nombre"])
        if params.get("codigo"):
            qs = qs.filter(codigo__iexact=params["codigo"])
        categoria_id = param_int(params, "categoria_id", minimo=1)
        if categoria_id:
            qs = qs.filter(categoria_id__in=ids_con_descendientes(categoria_id))
        proveedor_id = param_int(params, "proveedor_id", minimo=1)
        if proveedor_id:
            qs = qs.filter(proveedores__proveedor_id=proveedor_id)
        qs = qs.filter(activo=param_bool(params, "activo", defecto=True))
        items, total, page = paginar(qs, params)
        return Response({"total": total, "page": page, "results": ProductoSerializer(items, many=True).data})

    def post(self, request):
        exigir_rol(request, ADMIN)
        s = ProductoInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        categoria, unidad = _validar_referencias(datos)
        verificar_unico(Producto, "codigo", datos["codigo"], "un producto")
        producto = Producto()
        _aplicar(producto, datos, categoria, unidad)
        with guardar_o_409("Ya existe un producto con ese código"):
            producto.save()
        return Response(ProductoSerializer(producto).data, status=201)


class ProductoDetalleView(APIView):
    def get(self, request, pk):
        # Incluye productos inactivos: ms-existencias lee `activo` para rechazarlos él mismo (422).
        producto = Producto.objects.select_related("categoria", "unidad_medida") \
            .prefetch_related("proveedores__proveedor").filter(pk=pk).first()
        if producto is None:
            raise ErrorNegocio(404, "NO_ENCONTRADO", f"El producto {pk} no existe")
        return Response(ProductoDetalleSerializer(producto).data)

    def put(self, request, pk):
        """Actualiza datos; con `activo` permite reactivar o dar de baja. Omitido conserva el estado."""
        exigir_rol(request, ADMIN)
        producto = obtener_o_404(Producto, pk, "El producto")
        s = ProductoInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        activo = datos.get("activo", producto.activo)
        categoria, unidad = _validar_referencias(datos, exigir_categoria_activa=activo)
        verificar_unico(Producto, "codigo", datos["codigo"], "un producto", excluir_id=producto.pk)
        _aplicar(producto, datos, categoria, unidad)
        producto.activo = activo
        with guardar_o_409("Ya existe un producto con ese código"):
            producto.save()
        return Response(ProductoSerializer(producto).data)

    def delete(self, request, pk):
        exigir_rol(request, ADMIN)
        producto = obtener_o_404(Producto, pk, "El producto")
        producto.activo = False
        producto.save(update_fields=["activo"])
        return Response(status=204)


class ProductoProveedoresView(APIView):
    def post(self, request, pk):
        exigir_rol(request, ADMIN)
        producto = obtener_o_404(Producto, pk, "El producto")
        s = ProductoProveedorInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        proveedor = obtener_o_404(Proveedor, datos["proveedor_id"], "El proveedor")
        if not proveedor.activo:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El proveedor {proveedor.pk} está inactivo")
        if ProductoProveedor.objects.filter(producto=producto, proveedor=proveedor).exists():
            raise ErrorNegocio(409, "CONFLICTO",
                               f"El proveedor {proveedor.pk} ya está asociado al producto {producto.pk}")
        with guardar_o_409("El proveedor ya está asociado al producto"):
            with transaction.atomic():
                if datos["es_principal"]:
                    _desmarcar_principal(producto.pk)
                asociacion = ProductoProveedor.objects.create(
                    producto=producto, proveedor=proveedor,
                    precio_compra=datos["precio_compra"], es_principal=datos["es_principal"])
        return Response(ProductoProveedorSerializer(asociacion).data, status=201)


def _desmarcar_principal(producto_id):
    """Solo puede haber un proveedor principal por producto: se desmarca el actual."""
    ProductoProveedor.objects.filter(producto_id=producto_id, es_principal=True).update(es_principal=False)


class ProductoProveedorDetalleView(APIView):
    @staticmethod
    def _asociacion(pk, proveedor_id):
        obtener_o_404(Producto, pk, "El producto")
        asociacion = ProductoProveedor.objects.select_related("proveedor") \
            .filter(producto_id=pk, proveedor_id=proveedor_id).first()
        if asociacion is None:
            raise ErrorNegocio(404, "NO_ENCONTRADO",
                               f"El proveedor {proveedor_id} no está asociado al producto {pk}")
        return asociacion

    def put(self, request, pk, proveedor_id):
        """Cambia el precio de compra y/o el proveedor principal sin recrear la asociación."""
        exigir_rol(request, ADMIN)
        asociacion = self._asociacion(pk, proveedor_id)
        s = ProductoProveedorUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        with guardar_o_409("No se pudo actualizar la asociación por un cambio simultáneo"):
            with transaction.atomic():
                if datos.get("es_principal") and not asociacion.es_principal:
                    _desmarcar_principal(pk)
                asociacion.precio_compra = datos["precio_compra"]
                if "es_principal" in datos:
                    asociacion.es_principal = datos["es_principal"]
                asociacion.save(update_fields=["precio_compra", "es_principal"])
        return Response(ProductoProveedorSerializer(asociacion).data)

    def delete(self, request, pk, proveedor_id):
        exigir_rol(request, ADMIN)
        self._asociacion(pk, proveedor_id).delete()
        return Response(status=204)
