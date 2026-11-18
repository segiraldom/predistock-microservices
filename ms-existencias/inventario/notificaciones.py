"""
Cliente del microservicio de notificaciones (RF09).

La alerta se programa con transaction.on_commit: solo sale si el movimiento quedó guardado.
Si notificaciones no responde, se registra en el log y el movimiento no se ve afectado.
"""
import logging
import threading

import requests
from django.conf import settings
from django.db import transaction

log = logging.getLogger(__name__)


def numero(valor):
    """Decimal -> int si es entero, si no float (el contrato de alertas usa enteros)."""
    return int(valor) if valor == valor.to_integral_value() else float(valor)


def programar_alerta_stock_bajo(existencia):
    datos = {
        "alert_type": "LOW_STOCK_THRESHOLD",
        "product_id": existencia.producto_id,
        "warehouse_id": existencia.bodega_id,
        "current_stock": numero(existencia.cantidad),
        "threshold": numero(existencia.stock_minimo),
        "message": (f"Stock bajo: quedan {numero(existencia.cantidad)} unidades del producto "
                    f"{existencia.producto_id} en {existencia.bodega.nombre} "
                    f"(mínimo {numero(existencia.stock_minimo)})."),
    }
    transaction.on_commit(lambda: _despachar(datos))


def _despachar(datos):
    if settings.NOTIFICACIONES_ASINCRONO:
        threading.Thread(target=enviar_alerta, args=(datos,), daemon=True).start()
    else:
        enviar_alerta(datos)


def enviar_alerta(datos):
    base = settings.NOTIFICACIONES_SERVICE_URL
    if not base:
        return
    url = f"{base.rstrip('/')}/alerts"
    try:
        resp = requests.post(url, json=datos, timeout=settings.HTTP_TIMEOUT)
        if resp.status_code >= 400:
            log.warning("Notificaciones respondió %s a la alerta %s", resp.status_code, datos)
    except requests.RequestException as exc:
        log.warning("No se pudo enviar la alerta de stock bajo (%s): %s", url, exc)
