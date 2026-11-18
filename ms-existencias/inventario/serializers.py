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
