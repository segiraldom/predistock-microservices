from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class TrainedModel(Base):
    __tablename__ = 'trained_models'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_type = Column(String(50), nullable=False)   # 'kmeans_segmentation' | 'random_forest_demand'
    version = Column(String(20), nullable=False)
    file_path = Column(String(255), nullable=False)
    metrics = Column(JSON, nullable=True)             # {'r2': 0.81, 'rmse': 4.12, 'silhouette': 0.65}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    segmentations = relationship("InventorySegmentation", back_populates="model", cascade="all, delete-orphan")
    predictions = relationship("DemandPrediction", back_populates="model", cascade="all, delete-orphan")
    suggestions = relationship("StockSuggestion", back_populates="model", cascade="all, delete-orphan")

class InventorySegmentation(Base):
    __tablename__ = 'inventory_segmentation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey('trained_models.id'), nullable=False)
    product_id = Column(Integer, nullable=False, index=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    cluster_group = Column(Integer, nullable=False)   # 0: Baja rotación, 1: Media, 2: Alta rotación
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("TrainedModel", back_populates="segmentations")

class DemandPrediction(Base):
    __tablename__ = 'demand_predictions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey('trained_models.id'), nullable=False)
    product_id = Column(Integer, nullable=False, index=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    predicted_demand = Column(Float, nullable=False)
    target_period = Column(Date, nullable=False)       # Próximo mes o ciclo
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("TrainedModel", back_populates="predictions")

class StockSuggestion(Base):
    __tablename__ = 'stock_suggestions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey('trained_models.id'), nullable=False)
    product_id = Column(Integer, nullable=False, index=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    optimal_stock = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)        # 'RIESGO_QUIEBRE' | 'SOBRESTOCK' | 'OPTIMO'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("TrainedModel", back_populates="suggestions")