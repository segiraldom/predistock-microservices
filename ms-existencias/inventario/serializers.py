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
