from rest_framework import serializers

from .models import Categoria, Producto, ProductoProveedor, Proveedor, UnidadMedida

PRECIO = {"max_digits": 14, "decimal_places": 2}


# ---------- Unidades de medida ----------

class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = ["id", "codigo", "nombre"]
        read_only_fields = ["id"]
        # La unicidad del código se valida en la vista para responder 409 (contrato)
        extra_kwargs = {"codigo": {"validators": []}}


# ---------- Categorías ----------

class CategoriaSerializer(serializers.ModelSerializer):
    categoria_padre_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Categoria
        fields = ["id", "nombre", "descripcion", "categoria_padre_id", "activo"]


class CategoriaInputSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    descripcion = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    categoria_padre_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    activo = serializers.BooleanField(required=False)  # solo en PUT; omitido conserva el estado


# ---------- Proveedores ----------

class ProveedorSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=100, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Proveedor
        fields = ["id", "nit", "razon_social", "telefono", "email", "ciudad", "activo"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "nit": {"validators": []},
            "telefono": {"required": False, "allow_null": True, "allow_blank": True},
            "ciudad": {"required": False, "allow_null": True, "allow_blank": True},
            # Solo cuenta en PUT (reactivar o dar de baja); en POST siempre se crea activo
            "activo": {"required": False},
        }


# ---------- Productos ----------

class ProductoSerializer(serializers.ModelSerializer):
    categoria_id = serializers.IntegerField(read_only=True)
    unidad_medida_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Producto
        fields = ["id", "codigo", "nombre", "descripcion", "categoria_id", "unidad_medida_id",
                  "precio_venta", "costo", "es_perecedero", "activo"]


class ProductoProveedorSerializer(serializers.ModelSerializer):
    proveedor_id = serializers.IntegerField(read_only=True)
    razon_social = serializers.CharField(source="proveedor.razon_social", read_only=True)

    class Meta:
        model = ProductoProveedor
        fields = ["proveedor_id", "razon_social", "precio_compra", "es_principal"]


class ProductoDetalleSerializer(ProductoSerializer):
    """Detalle que consume ms-existencias: incluye categoría, unidad y proveedores."""
    categoria = CategoriaSerializer(read_only=True)
    unidad_medida = UnidadMedidaSerializer(read_only=True)
    proveedores = ProductoProveedorSerializer(many=True, read_only=True)

    class Meta(ProductoSerializer.Meta):
        fields = ProductoSerializer.Meta.fields + ["categoria", "unidad_medida", "proveedores"]


class ProductoInputSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=30)
    nombre = serializers.CharField(max_length=150)
    descripcion = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    categoria_id = serializers.IntegerField(min_value=1)
    unidad_medida_id = serializers.IntegerField(min_value=1)
    precio_venta = serializers.DecimalField(min_value=0, **PRECIO)
    costo = serializers.DecimalField(min_value=0, **PRECIO)
    es_perecedero = serializers.BooleanField(required=False, default=False)
    activo = serializers.BooleanField(required=False)  # solo en PUT; omitido conserva el estado


class ProductoProveedorInputSerializer(serializers.Serializer):
    proveedor_id = serializers.IntegerField(min_value=1)
    precio_compra = serializers.DecimalField(min_value=0, **PRECIO)
    es_principal = serializers.BooleanField(required=False, default=False)


class ProductoProveedorUpdateSerializer(serializers.Serializer):
    precio_compra = serializers.DecimalField(min_value=0, **PRECIO)
    es_principal = serializers.BooleanField(required=False)  # omitido conserva el valor
