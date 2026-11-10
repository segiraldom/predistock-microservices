import os
from datetime import datetime
from flask import Blueprint, jsonify
from app.config import Config
from app.database import get_db
from app.models.entities import TrainedModel, InventorySegmentation, DemandPrediction, StockSuggestion
from app.pipeline.collector import DataCollector
from app.pipeline.preprocessor import DataPipelineManager
from app.pipeline.clustering import train_inventory_segmentation
from app.pipeline.demand_predictor import train_demand_forecasting
from app.pipeline.inventory_rules import calculate_stock_suggestions

pipeline_bp = Blueprint('pipeline_bp', __name__, url_prefix='/api/analytics')

@pipeline_bp.route('/train', methods=['POST'])
def trigger_pipeline():
    """Ejecuta el ciclo de minería: extracción, modelado K-Means, Random Forest y cálculo de sugerencias."""
    models_dir = Config.MODELS_STORAGE_PATH
    os.makedirs(models_dir, exist_ok=True)
    db = next(get_db())
    version_id = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    try:
        # 1. Extracción e integración (RFM_01, RFM_02)
        collector = DataCollector()
        raw_df = collector.get_historical_movements()

        if raw_df.empty:
            return jsonify({"error": "No se encontraron movimientos históricos"}), 400

        # 2. Limpieza y escalado (RFM_03, RFM_04)
        preprocessor = DataPipelineManager()
        clean_df = preprocessor.clean_and_prepare(raw_df)

        # 3. Segmentación K-Means (RFM_05)
        summary_df, scaled_feat, _ = preprocessor.build_clustering_features(clean_df)
        kmeans_file = os.path.join(models_dir, f"kmeans_{version_id}.joblib")
        segmentation_res, kmeans_metrics = train_inventory_segmentation(summary_df, scaled_feat, kmeans_file)

        kmeans_record = TrainedModel(
            model_type="kmeans_segmentation",
            version=version_id,
            file_path=kmeans_file,
            metrics=kmeans_metrics
        )
        db.add(kmeans_record)
        db.flush()

        for _, row in segmentation_res.iterrows():
            db.add(InventorySegmentation(
                model_id=kmeans_record.id,
                product_id=int(row['producto_id']),
                warehouse_id=int(row['bodega_id']),
                cluster_group=int(row['cluster_group'])
            ))

        # 4. Regresión de Demanda Random Forest (RFM_06, RNFM_03)
        rf_file = os.path.join(models_dir, f"rf_demand_{version_id}.joblib")
        forecast_res, rf_metrics = train_demand_forecasting(clean_df, rf_file)

        rf_record = TrainedModel(
            model_type="random_forest_demand",
            version=version_id,
            file_path=rf_file,
            metrics=rf_metrics
        )
        db.add(rf_record)
        db.flush()

        for _, row in forecast_res.iterrows():
            db.add(DemandPrediction(
                model_id=rf_record.id,
                product_id=int(row['producto_id']),
                warehouse_id=int(row['bodega_id']),
                predicted_demand=float(row['predicted_demand']),
                target_period=row['target_period']
            ))

        # 5. Sugerencias de distribución y stock óptimo (RFM_07)
        stock_map = {(row['producto_id'], row['bodega_id']): 25 for _, row in forecast_res.iterrows()}
        suggestions_df = calculate_stock_suggestions(forecast_res, stock_map)

        for _, row in suggestions_df.iterrows():
            db.add(StockSuggestion(
                model_id=rf_record.id,
                product_id=int(row['product_id']),
                warehouse_id=int(row['warehouse_id']),
                optimal_stock=int(row['optimal_stock']),
                status=str(row['status'])
            ))

        db.commit()
        return jsonify({
            "status": "success",
            "version": version_id,
            "metrics": {
                "kmeans": kmeans_metrics,
                "random_forest": rf_metrics
            },
            "records_processed": len(clean_df)
        }), 201

    except ValueError as ve:
        db.rollback()
        return jsonify({"status": "rejected", "detail": str(ve)}), 422
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500