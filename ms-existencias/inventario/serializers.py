from rest_framework import serializers

from .models import Bodega, Existencia

CANTIDAD = {"max_digits": 14, "decimal_places": 3}


# ---------- Bodegas (RF05) ----------

class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = ["id", "codigo", "nombre", "region", "ciudad", "activa"]
        read_only_fields = ["id"]
        extra_kwargs = {
            # La unicidad del código se valida en la vista para responder 409 (contrato)
            "codigo": {"validators": []},
            "ciudad": {"required": False, "allow_null": True, "allow_blank": True},
            "activa": {"required": False},
        }


# ---------- Stock (RF04, RF05, RF09) ----------

class ExistenciaSerializer(serializers.ModelSerializer):
    """Salida. producto_nombre viene de catálogo a través de context['nombres']."""
    bodega_id = serializers.IntegerField(read_only=True)
    producto_nombre = serializers.SerializerMethodField()
    bajo_minimo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Existencia
        fields = ["id", "producto_id", "producto_nombre", "bodega_id",
                  "cantidad", "stock_minimo", "stock_maximo", "bajo_minimo"]

    def get_producto_nombre(self, obj):
        return self.context.get("nombres", {}).get(obj.producto_id)


def _validar_umbral(minimo, maximo):
    if maximo is not None and minimo is not None and maximo < minimo:
        raise serializers.ValidationError({"stock_maximo": "Debe ser mayor o igual que stock_minimo"})


class ExistenciaInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    bodega_id = serializers.IntegerField(min_value=1)
    stock_minimo = serializers.DecimalField(min_value=0, **CANTIDAD)
    stock_maximo = serializers.DecimalField(min_value=0, required=False, allow_null=True, **CANTIDAD)

    def validate(self, data):
        _validar_umbral(data["stock_minimo"], data.get("stock_maximo"))
        return data


class UmbralInputSerializer(serializers.Serializer):
    stock_minimo = serializers.DecimalField(min_value=0, **CANTIDAD)
    stock_maximo = serializers.DecimalField(min_value=0, required=False, allow_null=True, **CANTIDAD)


# ---------- Movimientos / kardex (RF04, RF10) ----------

from .models import Lote, Movimiento  # noqa: E402

TIPOS_MANUALES = ["ENTRADA", "SALIDA", "AJUSTE_ENTRADA", "AJUSTE_SALIDA"]


class MovimientoSerializer(serializers.ModelSerializer):
    bodega_id = serializers.IntegerField(read_only=True)
    lote_id = serializers.IntegerField(read_only=True)
    orden_compra_id = serializers.IntegerField(read_only=True)
    traslado_id = serializers.IntegerField(read_only=True)
    devolucion_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Movimiento
        fields = ["id", "producto_id", "bodega_id", "lote_id", "tipo", "cantidad", "saldo_resultante",
                  "orden_compra_id", "traslado_id", "devolucion_id", "usuario_id", "motivo", "fecha"]


class MovimientoInputSerializer(serializers.Serializer):
    """El usuario_id no se recibe: se toma de la cabecera X-Usuario-Id que pone el Gateway."""
    producto_id = serializers.IntegerField(min_value=1)
    bodega_id = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(choices=TIPOS_MANUALES)
    cantidad = serializers.DecimalField(**CANTIDAD)
    lote_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    numero_lote = serializers.CharField(required=False, max_length=30, allow_blank=False)
    fecha_vencimiento = serializers.DateField(required=False)
    motivo = serializers.CharField(required=False, max_length=255, allow_blank=True, allow_null=True)

    def validate_cantidad(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("Debe ser mayor que cero")
        return valor

    def validate(self, data):
        tipo = data["tipo"]
        if tipo.startswith("AJUSTE") and not (data.get("motivo") or "").strip():
            raise serializers.ValidationError({"motivo": "Es obligatorio en los ajustes"})
        tiene_numero, tiene_fecha = bool(data.get("numero_lote")), bool(data.get("fecha_vencimiento"))
        if tiene_numero or tiene_fecha:
            if tipo not in ("ENTRADA", "AJUSTE_ENTRADA"):
                raise serializers.ValidationError({"numero_lote": "Solo se indica en entradas; en salidas use lote_id"})
            if tiene_numero != tiene_fecha:
                raise serializers.ValidationError({"fecha_vencimiento": "numero_lote y fecha_vencimiento van juntos"})
            if data.get("lote_id"):
                raise serializers.ValidationError({"lote_id": "Indique lote_id o numero_lote, no ambos"})
        return data


# ---------- Lotes ----------

class LoteSerializer(serializers.ModelSerializer):
    bodega_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Lote
        fields = ["id", "producto_id", "bodega_id", "numero_lote", "fecha_vencimiento", "cantidad"]


class LoteCorreccionSerializer(serializers.Serializer):
    numero_lote = serializers.CharField(required=False, max_length=30, allow_blank=False)
    fecha_vencimiento = serializers.DateField(required=False)


# ---------- Documentos: traslados, devoluciones, órdenes de compra (RF04, RF06, RF13) ----------

from .models import (DetalleDevolucion, DetalleOrdenCompra, DetalleTraslado,  # noqa: E402
                     Devolucion, OrdenCompra, Traslado)


class CantidadPositiva(serializers.DecimalField):
    def __init__(self, **kwargs):
        super().__init__(**CANTIDAD, **kwargs)

    def to_internal_value(self, data):
        valor = super().to_internal_value(data)
        if valor <= 0:
            raise serializers.ValidationError("Debe ser mayor que cero")
        return valor


def _sin_productos_repetidos(lineas, campo="producto_id"):
    vistos = [l[campo] for l in lineas]
    if len(vistos) != len(set(vistos)):
        raise serializers.ValidationError(f"Hay {campo} repetidos en el detalle; agrupe las cantidades en una sola línea")
    return lineas


# Traslados

class LineaTrasladoSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    cantidad = CantidadPositiva()


class TrasladoInputSerializer(serializers.Serializer):
    bodega_origen_id = serializers.IntegerField(min_value=1)
    bodega_destino_id = serializers.IntegerField(min_value=1)
    sugerencia_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    detalle = LineaTrasladoSerializer(many=True, allow_empty=False)

    def validate_detalle(self, lineas):
        return _sin_productos_repetidos(lineas)

    def validate(self, data):
        if data["bodega_origen_id"] == data["bodega_destino_id"]:
            raise serializers.ValidationError({"bodega_destino_id": "La bodega destino debe ser distinta de la origen"})
        return data


class DetalleTrasladoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleTraslado
        fields = ["producto_id", "cantidad"]


class TrasladoSerializer(serializers.ModelSerializer):
    bodega_origen_id = serializers.IntegerField(read_only=True)
    bodega_destino_id = serializers.IntegerField(read_only=True)
    detalle = DetalleTrasladoSerializer(many=True, read_only=True)

    class Meta:
        model = Traslado
        fields = ["id", "bodega_origen_id", "bodega_destino_id", "sugerencia_id", "usuario_id", "fecha", "detalle"]


# Devoluciones

class LineaDevolucionSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    cantidad = CantidadPositiva()
    condicion = serializers.ChoiceField(choices=DetalleDevolucion.Condicion.values)


class DevolucionInputSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=Devolucion.Tipo.values)
    bodega_id = serializers.IntegerField(min_value=1)
    proveedor_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    referencia_cliente = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=50)
    motivo = serializers.CharField(max_length=255)
    detalle = LineaDevolucionSerializer(many=True, allow_empty=False)

    def validate_detalle(self, lineas):
        claves = [(l["producto_id"], l["condicion"]) for l in lineas]
        if len(claves) != len(set(claves)):
            raise serializers.ValidationError("Hay productos repetidos con la misma condición en el detalle")
        return lineas

    def validate(self, data):
        if data["tipo"] == "PROVEEDOR" and not data.get("proveedor_id"):
            raise serializers.ValidationError({"proveedor_id": "Es obligatorio en devoluciones a proveedor"})
        if data["tipo"] == "CLIENTE":
            data["proveedor_id"] = None
        else:
            data["referencia_cliente"] = None
        return data


class DetalleDevolucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleDevolucion
        fields = ["producto_id", "cantidad", "condicion"]


class DevolucionSerializer(serializers.ModelSerializer):
    bodega_id = serializers.IntegerField(read_only=True)
    detalle = DetalleDevolucionSerializer(many=True, read_only=True)

    class Meta:
        model = Devolucion
        fields = ["id", "tipo", "bodega_id", "proveedor_id", "referencia_cliente", "motivo",
                  "usuario_id", "fecha", "detalle"]


# Órdenes de compra

class LineaOrdenInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    cantidad_solicitada = CantidadPositiva()
    precio_unitario = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class OrdenCompraInputSerializer(serializers.Serializer):
    proveedor_id = serializers.IntegerField(min_value=1)
    bodega_id = serializers.IntegerField(min_value=1)
    detalle = LineaOrdenInputSerializer(many=True, allow_empty=False)

    def validate_detalle(self, lineas):
        return _sin_productos_repetidos(lineas)


class LineaOrdenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleOrdenCompra
        fields = ["id", "producto_id", "cantidad_solicitada", "cantidad_recibida", "precio_unitario"]


class OrdenCompraSerializer(serializers.ModelSerializer):
    bodega_id = serializers.IntegerField(read_only=True)
    detalle = LineaOrdenSerializer(many=True, read_only=True)

    class Meta:
        model = OrdenCompra
        fields = ["id", "numero", "proveedor_id", "bodega_id", "estado", "fecha_emision", "creada_por", "detalle"]


class EstadoOrdenInputSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=["CANCELADA"],
                                     error_messages={"invalid_choice": "Solo se puede cambiar manualmente a CANCELADA"})


class LineaRecepcionSerializer(serializers.Serializer):
    detalle_id = serializers.IntegerField(min_value=1)
    cantidad = CantidadPositiva()
    numero_lote = serializers.CharField(required=False, max_length=30, allow_blank=False)
    fecha_vencimiento = serializers.DateField(required=False)

    def validate(self, data):
        if bool(data.get("numero_lote")) != bool(data.get("fecha_vencimiento")):
            raise serializers.ValidationError({"fecha_vencimiento": "numero_lote y fecha_vencimiento van juntos"})
        return data


class RecepcionInputSerializer(serializers.Serializer):
    lineas = LineaRecepcionSerializer(many=True, allow_empty=False)

    def validate_lineas(self, lineas):
        return _sin_productos_repetidos(lineas, campo="detalle_id")
