import joblib
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

def train_inventory_segmentation(summary_df: pd.DataFrame, scaled_features: np.ndarray, model_path: str):
    """
    RFM_05: Segmentación no supervisada con K-Means.
    Clasifica los productos según volumen total y frecuencia de venta por bodega.
    
    Clusters normalizados:
      0: Baja Rotación (Candidatos a descontinuar o liquidar por riesgo de sobrestock/vencimiento)
      1: Media Rotación (Demanda estable y predecible)
      2: Alta Rotación (Productos críticos con alta demanda, requieren mayor stock de seguridad)
    """
    n_clusters = 3
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=15, max_iter=300)
    raw_clusters = kmeans.fit_predict(scaled_features)
    summary_df['cluster_raw'] = raw_clusters

    # Ordenar los IDs de cluster según el volumen promedio para garantizar consistencia semántica
    cluster_order = summary_df.groupby('cluster_raw')['volumen_total'].mean().sort_values().index
    mapping = {old_label: new_label for new_label, old_label in enumerate(cluster_order)}
    summary_df['cluster_group'] = summary_df['cluster_raw'].map(mapping)
    summary_df.drop(columns=['cluster_raw'], inplace=True)

    # Evaluación de calidad de la segmentación
    score = float(silhouette_score(scaled_features, summary_df['cluster_group']))

    # Guardar modelo entrenado
    joblib.dump(kmeans, model_path)

    metrics = {
        "silhouette_score": round(score, 4),
        "n_clusters": n_clusters,
        "inertia": round(float(kmeans.inertia_), 2)
    }

    return summary_df, metrics