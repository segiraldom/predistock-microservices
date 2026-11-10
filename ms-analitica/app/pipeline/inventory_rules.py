import pandas as pd

def calculate_stock_suggestions(predictions_df: pd.DataFrame, current_stock_map: dict):
    """
    Calcula stock de seguridad y stock óptimo:
    Stock Óptimo = Demanda Predicha + Stock de Seguridad (20%)
    Compara contra stock actual y clasifica:
    - RIESGO_QUIEBRE: Stock actual < 50% de la demanda predicha
    - SOBRESTOCK: Stock actual > 150% del stock óptimo
    - OPTIMO: Rango balanceado
    """
    suggestions = []
    for _, row in predictions_df.iterrows():
        pid = int(row['producto_id'])
        wid = int(row['warehouse_id']) if 'warehouse_id' in row else int(row['bodega_id'])
        pred_demand = float(row['predicted_demand'])

        # Stock de seguridad amortigua fluctuaciones
        safety_stock = int(round(pred_demand * 0.20))
        optimal_stock = int(round(pred_demand + safety_stock))

        current_qty = current_stock_map.get((pid, wid), 0)

        if current_qty < (pred_demand * 0.5):
            status = 'RIESGO_QUIEBRE'
        elif current_qty > (optimal_stock * 1.5):
            status = 'SOBRESTOCK'
        else:
            status = 'OPTIMO'

        suggestions.append({
            'product_id': pid,
            'warehouse_id': wid,
            'optimal_stock': optimal_stock,
            'status': status
        })
    return pd.DataFrame(suggestions)