def serialize_segmentation(record):
    return {
        "id": record.id,
        "product_id": record.product_id,
        "warehouse_id": record.warehouse_id,
        "cluster_group": record.cluster_group,
        "rotation_type": "Baja" if record.cluster_group == 0 else "Media" if record.cluster_group == 1 else "Alta",
        "updated_at": record.updated_at.isoformat() if record.updated_at else None
    }

def serialize_prediction(record):
    return {
        "id": record.id,
        "product_id": record.product_id,
        "warehouse_id": record.warehouse_id,
        "predicted_demand": round(record.predicted_demand, 2),
        "target_period": record.target_period.isoformat() if record.target_period else None,
        "generated_at": record.generated_at.isoformat() if record.generated_at else None
    }

def serialize_suggestion(record):
    return {
        "id": record.id,
        "product_id": record.product_id,
        "warehouse_id": record.warehouse_id,
        "optimal_stock": record.optimal_stock,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }