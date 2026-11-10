import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

class DataPipelineManager:
    def clean_and_prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """RFM_03: Tratamiento de nulos, inconsistencias y remoción de ruido (vectorizado)."""
        if df.empty:
            return df

        df = df.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce')
        df.dropna(subset=['producto_id', 'bodega_id', 'cantidad', 'fecha'], inplace=True)

        # Filtrar únicamente operaciones de salida/venta
        df = df[df['tipo'].isin(['SALIDA_VENTA', 'VENTA', 'DESPACHO'])]

        # Filtrado de outliers por IQR vectorizado (sin apply, sin warnings y preservando columnas)
        grouped = df.groupby(['producto_id', 'bodega_id'])['cantidad']
        q25 = grouped.transform(lambda x: x.quantile(0.25))
        q75 = grouped.transform(lambda x: x.quantile(0.75))
        iqr = q75 - q25

        lower_bound = np.maximum(0, q25 - 1.5 * iqr)
        upper_bound = q75 + 1.5 * iqr

        mask = (df['cantidad'] >= lower_bound) & (df['cantidad'] <= upper_bound)
        return df[mask].reset_index(drop=True)

    def build_clustering_features(self, df: pd.DataFrame):
        """RFM_04: Agregación y normalización para segmentación de rotación."""
        summary = df.groupby(['producto_id', 'bodega_id']).agg(
            frecuencia_ventas=('id', 'count'),
            volumen_total=('cantidad', 'sum'),
            ticket_promedio=('cantidad', 'mean')
        ).reset_index()

        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(summary[['frecuencia_ventas', 'volumen_total', 'ticket_promedio']])
        return summary, scaled_features, scaler