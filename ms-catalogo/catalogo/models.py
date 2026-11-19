"""
Modelo de datos de ms-catalogo, fiel a docs/db-diagram.txt.

La unicidad de códigos, NIT y nombres de categoría se exige en la base de datos sin distinguir
mayúsculas (índices sobre LOWER), para que dos peticiones simultáneas no puedan duplicarlos.
"""
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower


class Categoria(models.Model):
    """Categoría o subcategoría: con categoria_padre NULL es una categoría principal."""
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    categoria_padre = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="subcategorias")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "categorias"
        constraints = [
            # Nombre único por nivel. Son dos restricciones porque en SQL NULL no es igual a NULL:
            # una sola (nombre, padre) dejaría repetir nombres entre categorías principales.
            models.UniqueConstraint(Lower("nombre"), F("categoria_padre"), condition=Q(categoria_padre__isnull=False),
                                    name="uq_categoria_nombre_por_padre"),
            models.UniqueConstraint(Lower("nombre"), condition=Q(categoria_padre__isnull=True),
                                    name="uq_categoria_principal_nombre"),
        ]


class UnidadMedida(models.Model):
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=50)

    class Meta:
        db_table = "unidades_medida"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="uq_unidad_codigo")]


class Producto(models.Model):
    codigo = models.CharField(max_length=30)  # SKU o código de barras (RF01, RF12)
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
        constraints = [models.UniqueConstraint(Lower("codigo"), name="uq_producto_codigo")]
        indexes = [models.Index(fields=["nombre"], name="ix_producto_nombre")]


class Proveedor(models.Model):
    nit = models.CharField(max_length=20)
    razon_social = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    ciudad = models.CharField(max_length=80, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "proveedores"
        constraints = [models.UniqueConstraint(Lower("nit"), name="uq_proveedor_nit")]


class ProductoProveedor(models.Model):
    """Relación N:M entre productos y proveedores, con el precio de compra y el proveedor principal.

    Llave primaria compuesta (producto_id, proveedor_id), como en el diagrama (requiere Django 5.2).
    """
    pk = models.CompositePrimaryKey("producto_id", "proveedor_id")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="proveedores")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="productos")
    precio_compra = models.DecimalField(max_digits=14, decimal_places=2)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = "producto_proveedor"
        constraints = [
            # un solo proveedor principal por producto
            models.UniqueConstraint(fields=["producto"], condition=Q(es_principal=True),
                                    name="uq_producto_proveedor_principal"),
        ]
