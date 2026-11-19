"""Categorías y subcategorías (RF02): una sola tabla con relación recursiva."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..errores import ErrorNegocio
from ..identidad import ADMIN, exigir_rol
from ..models import Categoria
from ..serializers import CategoriaInputSerializer, CategoriaSerializer
from ..utils import guardar_o_409, obtener_o_404, param_bool, param_int, verificar_unico


def ids_con_descendientes(categoria_id):
    """La categoría y todas sus subcategorías (a cualquier profundidad)."""
    ids = {categoria_id}
    pendientes = [categoria_id]
    while pendientes:
        hijas = Categoria.objects.filter(categoria_padre_id__in=pendientes).values_list("id", flat=True)
        pendientes = [h for h in hijas if h not in ids]
        ids.update(pendientes)
    return ids


def _validar_padre(padre_id, categoria=None):
    """Devuelve el padre (o None). 400 si no existe, está inactivo o produciría un ciclo."""
    if padre_id is None:
        return None
    if categoria is not None and padre_id in ids_con_descendientes(categoria.pk):
        raise ErrorNegocio(400, "DATOS_INVALIDOS",
                           "La categoría no puede ser su propio padre ni de una de sus subcategorías (ciclo)")
    padre = Categoria.objects.filter(pk=padre_id).first()
    if padre is None:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La categoría padre {padre_id} no existe")
    if not padre.activo:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La categoría padre {padre_id} está inactiva")
    return padre


def _verificar_nombre(nombre, padre_id, excluir_id=None):
    verificar_unico(Categoria, "nombre", nombre, "una categoría en ese nivel", excluir_id=excluir_id,
                    categoria_padre_id=padre_id)


class CategoriaListaView(APIView):
    def get(self, request):
        padre_id = param_int(request.query_params, "padre_id", minimo=1)
        qs = Categoria.objects.order_by("id")
        qs = qs.filter(categoria_padre_id=padre_id) if padre_id else qs.filter(categoria_padre__isnull=True)
        qs = qs.filter(activo=param_bool(request.query_params, "activo", defecto=True))
        return Response(CategoriaSerializer(qs, many=True).data)

    def post(self, request):
        exigir_rol(request, ADMIN)
        s = CategoriaInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        padre = _validar_padre(datos.get("categoria_padre_id"))
        _verificar_nombre(datos["nombre"], padre.pk if padre else None)
        with guardar_o_409("Ya existe una categoría con ese nombre"):
            categoria = Categoria.objects.create(nombre=datos["nombre"], descripcion=datos.get("descripcion"),
                                                 categoria_padre=padre)
        return Response(CategoriaSerializer(categoria).data, status=201)


class CategoriaDetalleView(APIView):
    def put(self, request, pk):
        exigir_rol(request, ADMIN)
        categoria = obtener_o_404(Categoria, pk, "La categoría")
        s = CategoriaInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data
        padre = _validar_padre(datos.get("categoria_padre_id"), categoria)
        _verificar_nombre(datos["nombre"], padre.pk if padre else None, excluir_id=categoria.pk)
        categoria.nombre = datos["nombre"]
        categoria.descripcion = datos.get("descripcion")
        categoria.categoria_padre = padre
        with guardar_o_409("Ya existe una categoría con ese nombre"):
            categoria.save()
        return Response(CategoriaSerializer(categoria).data)

    def delete(self, request, pk):
        exigir_rol(request, ADMIN)
        categoria = obtener_o_404(Categoria, pk, "La categoría")
        productos = categoria.productos.filter(activo=True).count()
        subcategorias = categoria.subcategorias.filter(activo=True).count()
        if productos or subcategorias:
            raise ErrorNegocio(409, "CATEGORIA_EN_USO",
                               f"La categoría {categoria.nombre} tiene {productos} productos y "
                               f"{subcategorias} subcategorías activas y no puede darse de baja")
        categoria.activo = False
        categoria.save(update_fields=["activo"])
        return Response(status=204)
