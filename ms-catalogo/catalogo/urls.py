from django.urls import path

from .views.categorias import CategoriaDetalleView, CategoriaListaView
from .views.productos import (ProductoDetalleView, ProductoListaView, ProductoProveedorDetalleView,
                              ProductoProveedoresView)
from .views.proveedores import ProveedorDetalleView, ProveedorListaView
from .views.salud import salud
from .views.unidades import UnidadDetalleView, UnidadListaView

urlpatterns = [
    path("health", salud),
    # Productos (RF01, RF12) y asociación con proveedores (RF03)
    path("productos", ProductoListaView.as_view()),
    path("productos/<int:pk>", ProductoDetalleView.as_view()),  # consumido por ms-existencias
    path("productos/<int:pk>/proveedores", ProductoProveedoresView.as_view()),
    path("productos/<int:pk>/proveedores/<int:proveedor_id>", ProductoProveedorDetalleView.as_view()),
    # Categorías y subcategorías (RF02)
    path("categorias", CategoriaListaView.as_view()),
    path("categorias/<int:pk>", CategoriaDetalleView.as_view()),
    # Proveedores (RF03)
    path("proveedores", ProveedorListaView.as_view()),
    path("proveedores/<int:pk>", ProveedorDetalleView.as_view()),  # consumido por ms-existencias
    # Unidades de medida (RF01)
    path("unidades-medida", UnidadListaView.as_view()),
    path("unidades-medida/<int:pk>", UnidadDetalleView.as_view()),
]
