from django.urls import path

from .views.bodegas import BodegaDetalleView, BodegaListaView
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
]
