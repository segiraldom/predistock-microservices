"""
Modelo de datos de ms-existencias, fiel a docs/db-diagram.txt.

producto_id, proveedor_id y usuario_id son referencias lógicas a otros microservicios
(sin llave foránea física, RNF02); se validan por API.
"""
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Bodega(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    region = models.CharField(max_length=50)
    ciudad = models.CharField(max_length=80, null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "bodegas"


class Existencia(models.Model):
    """Saldo actual por producto y bodega. Solo se modifica a través de movimientos."""
    producto_id = models.IntegerField()
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="existencias")
    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_maximo = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)

    class Meta:
        db_table = "existencias"
        constraints = [
            models.UniqueConstraint(fields=["producto_id", "bodega"], name="uq_existencia_producto_bodega"),
            models.CheckConstraint(condition=Q(cantidad__gte=0), name="ck_existencia_cantidad_no_negativa"),
        ]
        indexes = [models.Index(fields=["bodega", "producto_id"], name="ix_existencia_bodega_prod")]

    @property
    def bajo_minimo(self):
        return self.cantidad < self.stock_minimo


class Lote(models.Model):
    producto_id = models.IntegerField()
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="lotes")
    numero_lote = models.CharField(max_length=30)
    fecha_vencimiento = models.DateField()
    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        db_table = "lotes"
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gte=0), name="ck_lote_cantidad_no_negativa"),
        ]
        indexes = [models.Index(fields=["fecha_vencimiento"], name="ix_lote_vencimiento")]


class OrdenCompra(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE"
        PARCIAL = "PARCIAL"
        RECIBIDA = "RECIBIDA"
        CANCELADA = "CANCELADA"

    numero = models.CharField(max_length=20, unique=True)
    proveedor_id = models.IntegerField()
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="ordenes_compra")
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_emision = models.DateField(default=timezone.localdate)
    creada_por = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "ordenes_compra"


class DetalleOrdenCompra(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="detalle")
    producto_id = models.IntegerField()
    cantidad_solicitada = models.DecimalField(max_digits=14, decimal_places=3)
    cantidad_recibida = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "detalle_orden_compra"


class Traslado(models.Model):
    bodega_origen = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="traslados_salida")
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="traslados_entrada")
    sugerencia_id = models.IntegerField(null=True, blank=True)  # referencia lógica a analítica (RFM_07)
    usuario_id = models.IntegerField(null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "traslados"
        constraints = [
            models.CheckConstraint(condition=~Q(bodega_origen=F("bodega_destino")), name="ck_traslado_bodegas_distintas"),
        ]


class DetalleTraslado(models.Model):
    traslado = models.ForeignKey(Traslado, on_delete=models.CASCADE, related_name="detalle")
    producto_id = models.IntegerField()
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        db_table = "detalle_traslado"


class Devolucion(models.Model):
    class Tipo(models.TextChoices):
        CLIENTE = "CLIENTE"
        PROVEEDOR = "PROVEEDOR"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="devoluciones")
    proveedor_id = models.IntegerField(null=True, blank=True)
    referencia_cliente = models.CharField(max_length=50, null=True, blank=True)
    motivo = models.CharField(max_length=255)
    usuario_id = models.IntegerField(null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "devoluciones"


class DetalleDevolucion(models.Model):
    class Condicion(models.TextChoices):
        APTO = "APTO"
        AVERIADO = "AVERIADO"

    devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name="detalle")
    producto_id = models.IntegerField()
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    condicion = models.CharField(max_length=10, choices=Condicion.choices)

    class Meta:
        db_table = "detalle_devolucion"


class Movimiento(models.Model):
    """Kardex (RF10): solo inserciones. Las correcciones se hacen con un movimiento de ajuste."""

    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA"
        SALIDA = "SALIDA"
        AJUSTE_ENTRADA = "AJUSTE_ENTRADA"
        AJUSTE_SALIDA = "AJUSTE_SALIDA"
        TRASLADO_ENTRADA = "TRASLADO_ENTRADA"
        TRASLADO_SALIDA = "TRASLADO_SALIDA"
        DEVOLUCION_CLIENTE = "DEVOLUCION_CLIENTE"
        DEVOLUCION_PROVEEDOR = "DEVOLUCION_PROVEEDOR"

    # Tipos que suman al saldo; el resto resta.
    TIPOS_ENTRADA = {"ENTRADA", "AJUSTE_ENTRADA", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE"}

    producto_id = models.IntegerField()
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="movimientos")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    saldo_resultante = models.DecimalField(max_digits=14, decimal_places=3)
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos")
    traslado = models.ForeignKey(Traslado, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos")
    devolucion = models.ForeignKey(Devolucion, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos")
    usuario_id = models.IntegerField(null=True, blank=True)
    motivo = models.CharField(max_length=255, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "movimientos"
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_movimiento_cantidad_positiva")]
        indexes = [
            models.Index(fields=["producto_id", "bodega", "-fecha"], name="ix_mov_prod_bod_fecha"),
            models.Index(fields=["tipo", "fecha"], name="ix_mov_tipo_fecha"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("Los movimientos del kardex no se modifican")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Los movimientos del kardex no se eliminan")
