# app/pipeline/seeder.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_historical_data() -> pd.DataFrame:
    """
    Genera transacciones históricas realistas modelando distribución ABC de inventario,
    estacionalidad comercial y multiplicadores por bodega regional.
    """
    np.random.seed(42)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    # 10 productos categorizados por comportamiento de rotación
    product_profiles = {
        # Alta Rotación (Clase A): Volúmenes altos, transacciones frecuentes
        1: {"base_weekly": 160, "freq_prob": 0.95, "cluster_expected": "Alta"},
        2: {"base_weekly": 140, "freq_prob": 0.90, "cluster_expected": "Alta"},
        3: {"base_weekly": 120, "freq_prob": 0.85, "cluster_expected": "Alta"},
        
        # Media Rotación (Clase B): Volúmenes moderados, frecuencia regular
        4: {"base_weekly": 50,  "freq_prob": 0.65, "cluster_expected": "Media"},
        5: {"base_weekly": 45,  "freq_prob": 0.60, "cluster_expected": "Media"},
        6: {"base_weekly": 40,  "freq_prob": 0.55, "cluster_expected": "Media"},
        7: {"base_weekly": 35,  "freq_prob": 0.50, "cluster_expected": "Media"},
        
        # Baja Rotación (Clase C): Volúmenes bajos, compras aisladas (riesgo stock)
        8: {"base_weekly": 8,   "freq_prob": 0.25, "cluster_expected": "Baja"},
        9: {"base_weekly": 6,   "freq_prob": 0.20, "cluster_expected": "Baja"},
        10: {"base_weekly": 4,  "freq_prob": 0.15, "cluster_expected": "Baja"}
    }
    
    # Ponderaciones por bodega regional
    warehouse_weights = {
        1: 1.25, # Bodega principal (mayor flujo)
        2: 1.00, # Bodega intermedia
        3: 0.80  # Bodega menor
    }
    
    records = []
    record_id = 1001

    # Recorremos 52 semanas del año
    for week_idx in range(52):
        week_date = start_date + timedelta(weeks=week_idx)
        month = week_date.month

        # Factor estacional: incrementos en primas (mes 6) y festividades (meses 11 y 12)
        seasonality = 1.0
        if month in [6, 7]:
            seasonality = 1.15
        elif month in [11, 12]:
            seasonality = 1.30

        for wid, w_factor in warehouse_weights.items():
            for pid, profile in product_profiles.items():
                # Probabilidad de venta en la semana según rotación
                if np.random.rand() <= profile["freq_prob"]:
                    # Cantidad esperada modelada con ruido Gaussiano controlado
                    base = profile["base_weekly"] * w_factor * seasonality
                    qty = np.random.normal(loc=base, scale=base * 0.08)
                    final_qty = max(1, int(round(qty)))

                    # Día aleatorio dentro de la semana
                    tx_date = week_date + timedelta(days=int(np.random.randint(0, 7)))

                    records.append({
                        "id": record_id,
                        "producto_id": pid,
                        "bodega_id": wid,
                        "tipo": "SALIDA_VENTA",
                        "cantidad": final_qty,
                        "fecha": tx_date.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    record_id += 1

    return pd.DataFrame(records)