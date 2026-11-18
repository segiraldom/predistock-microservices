from django.urls import path

from .views.bodegas import BodegaDetalleView, BodegaListaView
from .views.lotes import LoteDetalleView, LotesView
from .views.movimientos import HistoricoView, MovimientosView
from .views.salud import salud
from .views.stock import StockView, UmbralView

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
]
