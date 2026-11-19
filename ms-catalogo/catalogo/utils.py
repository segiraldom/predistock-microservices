"""Utilidades de lectura de parámetros, búsqueda de recursos y unicidad."""
from contextlib import contextmanager

from django.db import IntegrityError, transaction

from .errores import ErrorNegocio

VERDADEROS = {"true", "1", "si", "sí"}
FALSOS = {"false", "0", "no"}


def param_bool(query_params, nombre, defecto=None):
    valor = query_params.get(nombre)
    if valor is None or valor == "":
        return defecto
    valor = valor.strip().lower()
    if valor in VERDADEROS:
        return True
    if valor in FALSOS:
        return False
    raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' debe ser true o false")


def param_int(query_params, nombre, defecto=None, minimo=None, maximo=None):
    valor = query_params.get(nombre)
    if valor is None or valor == "":
        return defecto
    try:
        numero = int(valor)
    except ValueError:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' debe ser un entero")
    if minimo is not None and numero < minimo:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' debe ser mayor o igual a {minimo}")
    if maximo is not None and numero > maximo:
        numero = maximo
    return numero


def paginar(queryset, query_params):
    """Paginación del contrato (page, page_size<=100). Devuelve (items, total, page)."""
    page = param_int(query_params, "page", 1, minimo=1)
    page_size = param_int(query_params, "page_size", 20, minimo=1, maximo=100)
    total = queryset.count()
    inicio = (page - 1) * page_size
    return list(queryset[inicio:inicio + page_size]), total, page


def obtener_o_404(modelo, pk, descripcion):
    objeto = modelo.objects.filter(pk=pk).first()
    if objeto is None:
        raise ErrorNegocio(404, "NO_ENCONTRADO", f"{descripcion} {pk} no existe")
    return objeto


def verificar_unico(modelo, campo, valor, descripcion, excluir_id=None, **filtros):
    """409 si ya existe otro registro con ese valor (sin distinguir mayúsculas)."""
    qs = modelo.objects.filter(**{f"{campo}__iexact": valor}, **filtros)
    if excluir_id is not None:
        qs = qs.exclude(pk=excluir_id)
    if qs.exists():
        raise ErrorNegocio(409, "CONFLICTO", f"Ya existe {descripcion} con {campo.replace('_', ' ')} {valor}")


@contextmanager
def guardar_o_409(mensaje):
    """Atomiza la escritura y convierte una violación de unicidad (carrera entre dos peticiones) en 409."""
    try:
        with transaction.atomic():
            yield
    except IntegrityError:
        raise ErrorNegocio(409, "CONFLICTO", mensaje)
