"""
Reglas de negocio del kardex. Regla central: todo cambio de stock es un movimiento,
y todo movimiento actualiza existencias (y lotes) en la misma transacción.

Lo usan movimientos manuales, traslados, devoluciones y recepciones de órdenes de compra.
"""
from django.utils import timezone

from . import catalogo, notificaciones
from .errores import ErrorNegocio
from .identidad import OPERADOR_BODEGA
from .models import Bodega, Existencia, Lote, Movimiento

TIPOS_ENTRADA = Movimiento.TIPOS_ENTRADA
TIPOS_CON_LOTE_OBLIGATORIO = {"ENTRADA", "AJUSTE_ENTRADA"}


def texto(valor):
    """Decimal('80.000') -> '80' para mensajes legibles."""
    return f"{valor.normalize():f}"


def stock_insuficiente(disponible, solicitado, producto_id, bodega_id, detalle=""):
    return ErrorNegocio(
        409, "STOCK_INSUFICIENTE",
        f"Disponible {texto(disponible)}{detalle}, solicitado {texto(solicitado)} "
        f"(producto {producto_id}, bodega {bodega_id})",
    )


def bodega_operable(identidad, bodega_id):
    """Bodega existente y activa; un operador solo puede operar la bodega asignada en su token."""
    bodega = Bodega.objects.filter(pk=bodega_id).first()
    if bodega is None:
        raise ErrorNegocio(400, "DATOS_INVALIDOS", f"La bodega {bodega_id} no existe")
    if not bodega.activa:
        raise ErrorNegocio(400, "BODEGA_INACTIVA", f"La bodega {bodega_id} está inactiva")
    if identidad.rol == OPERADOR_BODEGA and identidad.bodega_id != bodega.pk:
        raise ErrorNegocio(403, "BODEGA_NO_ASIGNADA",
                           f"El operador solo puede registrar movimientos en su bodega asignada")
    return bodega


def _bloquear_existencia(producto_id, bodega, crear):
    """Lee el saldo con bloqueo de fila (SELECT ... FOR UPDATE) para evitar carreras."""
    existencia = Existencia.objects.select_for_update().filter(producto_id=producto_id, bodega=bodega).first()
    if existencia is not None:
        return existencia
    if not crear:
        raise ErrorNegocio(422, "PRODUCTO_NO_REGISTRADO",
                           f"El producto {producto_id} no está registrado en la bodega {bodega.pk}; "
                           f"regístrelo primero en /stock")
    nueva, _ = Existencia.objects.get_or_create(
        producto_id=producto_id, bodega=bodega, defaults={"cantidad": 0, "stock_minimo": 0})
    return Existencia.objects.select_for_update().get(pk=nueva.pk)


def _lote_del_producto(lote_id, producto_id, bodega):
    lote = Lote.objects.select_for_update().filter(pk=lote_id, producto_id=producto_id, bodega=bodega).first()
    if lote is None:
        raise ErrorNegocio(400, "LOTE_INVALIDO",
                           f"El lote {lote_id} no pertenece al producto {producto_id} en la bodega {bodega.pk}")
    return lote


def _lote_para_entrada(tipo, producto_id, bodega, perecedero, lote_id, numero_lote, fecha_vencimiento):
    if lote_id:
        return _lote_del_producto(lote_id, producto_id, bodega)
    if numero_lote:
        lote = Lote.objects.select_for_update().filter(
            producto_id=producto_id, bodega=bodega, numero_lote=numero_lote).first()
        if lote is None:
            return Lote.objects.create(producto_id=producto_id, bodega=bodega, numero_lote=numero_lote,
                                       fecha_vencimiento=fecha_vencimiento, cantidad=0)
        if fecha_vencimiento and lote.fecha_vencimiento != fecha_vencimiento:
            raise ErrorNegocio(400, "LOTE_INCONSISTENTE",
                               f"El lote {numero_lote} ya existe con vencimiento {lote.fecha_vencimiento}")
        return lote
    if perecedero and tipo in TIPOS_CON_LOTE_OBLIGATORIO:
        raise ErrorNegocio(400, "LOTE_REQUERIDO",
                           f"El producto {producto_id} es perecedero: indique numero_lote y fecha_vencimiento")
    return None


def _consumos_de_salida(tipo, existencia, cantidad, perecedero, lote_id):
    """Lista de (lote | None, cantidad) a descontar. Sin lote_id aplica FEFO (vence primero, sale primero)."""
    producto_id, bodega = existencia.producto_id, existencia.bodega

    if lote_id:
        lote = _lote_del_producto(lote_id, producto_id, bodega)
        if lote.cantidad < cantidad:
            raise stock_insuficiente(lote.cantidad, cantidad, producto_id, bodega.pk, f" en el lote {lote.numero_lote}")
        return [(lote, cantidad)]

    lotes = Lote.objects.select_for_update().filter(
        producto_id=producto_id, bodega=bodega, cantidad__gt=0).order_by("fecha_vencimiento", "id")
    # Si catálogo no dice si es perecedero, se usan lotes cuando el producto los tiene
    usar_lotes = perecedero is True or (perecedero is None and lotes.exists())
    if not usar_lotes:
        return [(None, cantidad)]

    if tipo == "SALIDA":  # no se despachan lotes vencidos; para darlos de baja se usa AJUSTE_SALIDA
        lotes = lotes.filter(fecha_vencimiento__gte=timezone.localdate())

    consumos, pendiente = [], cantidad
    for lote in lotes:
        if pendiente <= 0:
            break
        tomar = min(lote.cantidad, pendiente)
        consumos.append((lote, tomar))
        pendiente -= tomar
    if pendiente > 0:
        raise stock_insuficiente(cantidad - pendiente, cantidad, producto_id, bodega.pk, " en lotes vigentes")
    return consumos


def registrar_movimiento(*, producto_id, bodega, tipo, cantidad, usuario_id, motivo=None,
                         lote_id=None, numero_lote=None, fecha_vencimiento=None,
                         orden_compra=None, traslado=None, devolucion=None,
                         crear_existencia=False, perecedero="consultar"):
    """
    Aplica un movimiento al kardex. DEBE llamarse dentro de transaction.atomic().

    Devuelve la lista de movimientos creados: normalmente uno, pero una salida que
    consume varios lotes (FEFO) genera un movimiento por lote para conservar la trazabilidad.
    """
    existencia = _bloquear_existencia(producto_id, bodega, crear_existencia)
    if perecedero == "consultar":
        perecedero = catalogo.es_perecedero(producto_id)
    referencias = {"orden_compra": orden_compra, "traslado": traslado, "devolucion": devolucion,
                   "usuario_id": usuario_id, "motivo": motivo}

    if tipo in TIPOS_ENTRADA:
        lote = _lote_para_entrada(tipo, producto_id, bodega, perecedero, lote_id, numero_lote, fecha_vencimiento)
        consumos = [(lote, cantidad)]
        signo = 1
    else:
        if existencia.cantidad < cantidad:
            raise stock_insuficiente(existencia.cantidad, cantidad, producto_id, bodega.pk)
        consumos = _consumos_de_salida(tipo, existencia, cantidad, perecedero, lote_id)
        signo = -1

    movimientos = []
    for lote, parte in consumos:
        existencia.cantidad += signo * parte
        if lote is not None:
            lote.cantidad += signo * parte
            lote.save(update_fields=["cantidad"])
        movimientos.append(Movimiento.objects.create(
            producto_id=producto_id, bodega=bodega, lote=lote, tipo=tipo, cantidad=parte,
            saldo_resultante=existencia.cantidad, **referencias))
    existencia.save(update_fields=["cantidad"])

    if signo < 0 and existencia.bajo_minimo:
        notificaciones.programar_alerta_stock_bajo(existencia)
    return movimientos
