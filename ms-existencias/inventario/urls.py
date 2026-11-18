from django.urls import path

from .views.bodegas import BodegaDetalleView, BodegaListaView
from .views.devoluciones import DevolucionDetalleView, DevolucionesView
from .views.lotes import LoteDetalleView, LotesView
from .views.movimientos import HistoricoView, MovimientosView
from .views.ordenes import OrdenDetalleView, OrdenEstadoView, OrdenesView, RecepcionesView
from .views.salud import salud
from .views.stock import StockView, UmbralView
from .views.traslados import TrasladoDetalleView, TrasladosView

urlpatterns = [
    path("health", salud),
    # Bodegas (RF05)
    path("bodegas", BodegaListaView.as_view()),
    path("bodegas/<int:pk>", BodegaDetalleView.as_view()),
    # Stock (RF04, RF05, RF09)
    path("stock", StockView.as_view()),
    path("stock/<int:pk>/umbral", UmbralView.as_view()),
    # Movimientos / kardex (RF04, RF10)
    path("movimientos", MovimientosView.as_view()),
    path("movimientos/historico", HistoricoView.as_view()),  # consumido por ms-analitica
    # Lotes
    path("lotes", LotesView.as_view()),
    path("lotes/<int:pk>", LoteDetalleView.as_view()),
    # Órdenes de compra (RF06)
    path("ordenes-compra", OrdenesView.as_view()),
    path("ordenes-compra/<int:pk>", OrdenDetalleView.as_view()),
    path("ordenes-compra/<int:pk>/estado", OrdenEstadoView.as_view()),
    path("ordenes-compra/<int:pk>/recepciones", RecepcionesView.as_view()),
    # Traslados (RF04)
    path("traslados", TrasladosView.as_view()),
    path("traslados/<int:pk>", TrasladoDetalleView.as_view()),
    # Devoluciones (RF13)
    path("devoluciones", DevolucionesView.as_view()),
    path("devoluciones/<int:pk>", DevolucionDetalleView.as_view()),
]
