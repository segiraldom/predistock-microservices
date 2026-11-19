"""
Modelo de datos de ms-catalogo, fiel a docs/db-diagram.txt.

Única diferencia: producto_proveedor tiene un id propio además de la restricción de unicidad
(producto, proveedor), porque Django 5.0/5.1 no soporta llaves primarias compuestas.
"""
from django.db import models
from django.db.models import Q


class Categoria(models.Model):
    """Categoría o subcategoría: con categoria_padre NULL es una categoría principal."""
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    categoria_padre = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="subcategorias")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "categorias"


class UnidadMedida(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        db_table = "unidades_medida"


class Producto(models.Model):
    codigo = models.CharField(max_length=30, unique=True)  # SKU o código de barras (RF01, RF12)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name="productos")
    precio_venta = models.DecimalField(max_digits=14, decimal_places=2)
    costo = models.DecimalField(max_digits=14, decimal_places=2)
    es_perecedero = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "productos"
        indexes = [models.Index(fields=["nombre"], name="ix_producto_nombre")]


class Proveedor(models.Model):
    nit = models.CharField(max_length=20, unique=True)
    razon_social = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    ciudad = models.CharField(max_length=80, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "proveedores"


class ProductoProveedor(models.Model):
    """Relación N:M entre productos y proveedores, con el precio de compra y el proveedor principal."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="proveedores")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="productos")
    precio_compra = models.DecimalField(max_digits=14, decimal_places=2)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = "producto_proveedor"
        constraints = [
            models.UniqueConstraint(fields=["producto", "proveedor"], name="uq_producto_proveedor"),
            # un solo proveedor principal por producto
            models.UniqueConstraint(fields=["producto"], condition=Q(es_principal=True),
                                    name="uq_producto_proveedor_principal"),
        ]
