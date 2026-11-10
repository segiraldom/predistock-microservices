from flask import Blueprint, jsonify, request
from sqlalchemy import desc, func
from app.database import get_db
from app.models.entities import InventorySegmentation, DemandPrediction, StockSuggestion, TrainedModel
from app.utils.serializers import serialize_segmentation, serialize_prediction, serialize_suggestion

reports_bp = Blueprint('reports_bp', __name__, url_prefix='/api/analytics')

def _get_latest_model_id(db, model_type: str):
    """Obtiene el ID del último modelo entrenado exitosamente según su tipo."""
    return db.query(func.max(TrainedModel.id)).filter(TrainedModel.model_type == model_type).scalar()

@reports_bp.route('/segmentation', methods=['GET'])
def get_segmentation():
    warehouse_id = request.args.get('warehouse_id', type=int)
    db = next(get_db())
    
    latest_id = _get_latest_model_id(db, 'kmeans_segmentation')
    if not latest_id:
        return jsonify([]), 200

    query = db.query(InventorySegmentation).filter(InventorySegmentation.model_id == latest_id)
    if warehouse_id:
        query = query.filter(InventorySegmentation.warehouse_id == warehouse_id)

    results = query.order_by(InventorySegmentation.product_id).all()
    return jsonify([serialize_segmentation(r) for r in results]), 200

@reports_bp.route('/predictions', methods=['GET'])
def get_predictions():
    warehouse_id = request.args.get('warehouse_id', type=int)
    db = next(get_db())
    
    latest_id = _get_latest_model_id(db, 'random_forest_demand')
    if not latest_id:
        return jsonify([]), 200

    query = db.query(DemandPrediction).filter(DemandPrediction.model_id == latest_id)
    if warehouse_id:
        query = query.filter(DemandPrediction.warehouse_id == warehouse_id)

    results = query.order_by(DemandPrediction.product_id).all()
    return jsonify([serialize_prediction(r) for r in results]), 200

@reports_bp.route('/suggestions', methods=['GET'])
def get_suggestions():
    status = request.args.get('status')
    warehouse_id = request.args.get('warehouse_id', type=int)
    db = next(get_db())
    
    latest_id = _get_latest_model_id(db, 'random_forest_demand')
    if not latest_id:
        return jsonify([]), 200

    query = db.query(StockSuggestion).filter(StockSuggestion.model_id == latest_id)
    if status:
        query = query.filter(StockSuggestion.status == status.upper())
    if warehouse_id:
        query = query.filter(StockSuggestion.warehouse_id == warehouse_id)

    results = query.order_by(StockSuggestion.product_id).all()
    return jsonify([serialize_suggestion(r) for r in results]), 200