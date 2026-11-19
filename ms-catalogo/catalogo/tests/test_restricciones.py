"""
Restricciones en la base de datos (no solo en las vistas): protegen contra dos peticiones
simultáneas que pasen ambas la verificación previa. Se prueban directamente con el ORM.
"""
from django.db import IntegrityError, transaction

from catalogo.models import Categoria, ProductoProveedor, Proveedor, UnidadMedida

from .base import BaseAPITest


class RestriccionesBDTest(BaseAPITest):
    def assertDuplicado(self, crear):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear()

    def test_codigo_de_producto_unico_sin_mayusculas(self):
        p = self.crear_producto(codigo="LAC-001")
        self.assertDuplicado(lambda: self.crear_producto(categoria=p.categoria, unidad=p.unidad_medida,
                                                         codigo="lac-001"))

    def test_codigo_de_unidad_unico_sin_mayusculas(self):
        UnidadMedida.objects.create(codigo="UND", nombre="Unidad")
        self.assertDuplicado(lambda: UnidadMedida.objects.create(codigo="und", nombre="Otra"))

    def test_nit_unico_sin_mayusculas(self):
        Proveedor.objects.create(nit="900ABC", razon_social="A")
        self.assertDuplicado(lambda: Proveedor.objects.create(nit="900abc", razon_social="B"))

    def test_nombre_de_categoria_principal_unico(self):
        Categoria.objects.create(nombre="Lácteos")
        self.assertDuplicado(lambda: Categoria.objects.create(nombre="LÁCTEOS".lower()))

    def test_nombre_de_subcategoria_unico_por_padre(self):
        padre = Categoria.objects.create(nombre="Alimentos")
        Categoria.objects.create(nombre="Lácteos", categoria_padre=padre)
        self.assertDuplicado(lambda: Categoria.objects.create(nombre="lácteos", categoria_padre=padre))

    def test_mismo_nombre_con_otro_padre_es_valido(self):
        a = Categoria.objects.create(nombre="A")
        b = Categoria.objects.create(nombre="B")
        Categoria.objects.create(nombre="Otros", categoria_padre=a)
        Categoria.objects.create(nombre="Otros", categoria_padre=b)
        Categoria.objects.create(nombre="Otros")
        self.assertEqual(Categoria.objects.filter(nombre="Otros").count(), 3)

    def test_llave_compuesta_impide_asociacion_duplicada(self):
        p = self.crear_producto()
        prov = self.crear_proveedor()
        ProductoProveedor.objects.create(producto=p, proveedor=prov, precio_compra=1)
        self.assertDuplicado(lambda: ProductoProveedor.objects.create(producto=p, proveedor=prov, precio_compra=2))
        self.assertEqual(ProductoProveedor.objects.get(producto=p, proveedor=prov).pk, (p.id, prov.id))

    def test_un_solo_principal_por_producto(self):
        p = self.crear_producto()
        ProductoProveedor.objects.create(producto=p, proveedor=self.crear_proveedor("1"), precio_compra=1,
                                         es_principal=True)
        self.assertDuplicado(lambda: ProductoProveedor.objects.create(
            producto=p, proveedor=self.crear_proveedor("2"), precio_compra=1, es_principal=True))
