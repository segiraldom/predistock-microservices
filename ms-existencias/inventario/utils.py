"""Utilidades de lectura de parámetros y búsqueda de recursos."""
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
    """Paginación del contrato (page, page_size<=100). Devuelve (items, total)."""
    page = param_int(query_params, "page", 1, minimo=1)
    page_size = param_int(query_params, "page_size", 20, minimo=1, maximo=100)
    total = queryset.count()
    inicio = (page - 1) * page_size
    return list(queryset[inicio:inicio + page_size]), total


def obtener_o_404(modelo, pk, descripcion):
    objeto = modelo.objects.filter(pk=pk).first()
    if objeto is None:
        raise ErrorNegocio(404, "NO_ENCONTRADO", f"{descripcion} {pk} no existe")
    return objeto


def param_fecha(query_params, nombre, obligatorio=False):
    from datetime import date
    valor = query_params.get(nombre)
    if not valor:
        if obligatorio:
            raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' es obligatorio (AAAA-MM-DD)")
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' debe tener formato AAAA-MM-DD")


def param_opcion(query_params, nombre, opciones):
    valor = query_params.get(nombre)
    if valor and valor not in opciones:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"El parámetro '{nombre}' debe ser uno de: {', '.join(sorted(opciones))}")
    return valor or None
