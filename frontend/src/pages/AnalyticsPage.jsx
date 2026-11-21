import { useState, useEffect, useMemo } from 'react';
import { Play, TrendingUp, Layers, PackageCheck, AlertCircle, CheckCircle2, XCircle, Clock, Database } from 'lucide-react';
import gatewayClient from '../api/gatewayClient';

const FALLBACK_PRODUCTS = {
  1: 'Arroz Blanco Premium 5kg',
  2: 'Aceite Vegetal 1L',
  3: 'Leche Entera UHT x6',
  4: 'Café Molido Tradicional 500g',
  5: 'Azúcar Refinada 2kg',
  6: 'Pasta Espagueti 500g',
  7: 'Atún en Aceite 170g',
  8: 'Frijol Bola Roja 1kg',
  9: 'Harina de Maíz 1kg',
  10: 'Sal Yodada 1kg',
};

export default function AnalyticsPage() {
  const [warehouseId, setWarehouseId] = useState(1);
  const [segmentation, setSegmentation] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [catalogProducts, setCatalogProducts] = useState([]);

  const [trainResult, setTrainResult] = useState(() => {
    const saved = sessionStorage.getItem('predistock_train_result');
    return saved ? JSON.parse(saved) : null;
  });
  const [training, setTraining] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');

  const productNamesMap = useMemo(() => {
    const map = { ...FALLBACK_PRODUCTS };
    catalogProducts.forEach((p) => {
      if (p.id && (p.nombre || p.name)) {
        map[p.id] = p.nombre || p.name;
      }
    });
    return map;
  }, [catalogProducts]);

  const getProductName = (productId) => productNamesMap[productId] || `Producto #${productId}`;

  useEffect(() => {
    gatewayClient.get('/catalogo/productos')
      .then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data?.results || []);
        setCatalogProducts(items);
      })
      .catch(() => setCatalogProducts([]));
  }, []);

  const fetchAnalyticsData = async () => {
    setLoadingData(true);
    setError('');
    try {
      const [segRes, predRes, sugRes] = await Promise.all([
        gatewayClient.get(`/analytics/segmentation?warehouse_id=${warehouseId}`),
        gatewayClient.get(`/analytics/predictions?warehouse_id=${warehouseId}`),
        gatewayClient.get(`/analytics/suggestions?warehouse_id=${warehouseId}`),
      ]);

      setSegmentation(Array.isArray(segRes.data) ? segRes.data : []);
      setPredictions(Array.isArray(predRes.data) ? predRes.data : []);
      setSuggestions(Array.isArray(sugRes.data) ? sugRes.data : []);
    } catch (err) {
      setError(err.friendlyMessage || 'Error al consultar el pipeline de analítica.');
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    fetchAnalyticsData();
  }, [warehouseId]);

  const handleTrainPipeline = async () => {
    setTraining(true);
    setError('');
    try {
      const { data } = await gatewayClient.post('/analytics/train');
      const r2 = Number(data.metrics?.random_forest?.r2_score ?? 0);
      const silhouette = Number(data.metrics?.kmeans?.silhouette_score ?? 0);

      const resultPayload = {
        r2,
        silhouette,
        approved: r2 >= 0.70,
        version: data.version || 'N/A',
        recordsProcessed: data.records_processed ?? 0,
        trainedAt: new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      };

      setTrainResult(resultPayload);
      sessionStorage.setItem('predistock_train_result', JSON.stringify(resultPayload));
      await fetchAnalyticsData();
    } catch (err) {
      const rejectedMetrics = err.response?.data?.metrics;
      if (rejectedMetrics) {
        const r2 = Number(rejectedMetrics.random_forest?.r2_score ?? 0);
        const silhouette = Number(rejectedMetrics.kmeans?.silhouette_score ?? 0);
        const resultPayload = {
          r2,
          silhouette,
          approved: false,
          version: err.response?.data?.version || 'Rechazado',
          recordsProcessed: err.response?.data?.records_processed ?? 0,
          trainedAt: new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        };
        setTrainResult(resultPayload);
        sessionStorage.setItem('predistock_train_result', JSON.stringify(resultPayload));
      } else {
        setError(err.response?.data?.detail || err.response?.data?.error || err.friendlyMessage || 'Error ejecutando el entrenamiento de modelos.');
      }
    } finally {
      setTraining(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-5 rounded-lg shadow-sm border border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Analítica Predictiva y Minería (ML)</h1>
          <p className="text-sm text-slate-500">Segmentación K-Means, Pronóstico Random Forest y Optimización de Stock</p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={warehouseId}
            onChange={(e) => setWarehouseId(Number(e.target.value))}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm bg-slate-50"
          >
            <option value={1}>Bodega Central (ID: 1)</option>
            <option value={2}>Bodega Norte (ID: 2)</option>
            <option value={3}>Bodega Sur (ID: 3)</option>
          </select>

          <button
            onClick={handleTrainPipeline}
            disabled={training}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
          >
            <Play className="w-4 h-4" />
            {training ? 'Entrenando...' : 'Ejecutar Pipeline ML'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-center gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {trainResult && (
        <div className={`border p-4 rounded-lg flex flex-wrap items-center justify-between gap-4 ${
          trainResult.approved
            ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
            : 'bg-red-50 border-red-200 text-red-900'
        }`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <span className="text-xs font-semibold uppercase opacity-75">Random Forest (RNFM_03)</span>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-lg font-bold">R² Score: {trainResult.r2.toFixed(4)}</p>
                {trainResult.approved ? (
                  <span className="inline-flex items-center gap-1 text-xs bg-emerald-200 text-emerald-900 px-2 py-0.5 rounded font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {'Aprobado (≥ 0.70)'}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs bg-red-200 text-red-900 px-2 py-0.5 rounded font-medium">
                    <XCircle className="w-3.5 h-3.5" /> {'Rechazado (< 0.70) - Modelo previo conservado'}
                  </span>
                )}
              </div>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase opacity-75">Clustering K-Means (RFM_05)</span>
              <p className="text-lg font-bold mt-0.5">Silhouette Score: {trainResult.silhouette.toFixed(4)}</p>
            </div>
          </div>

          <div className="flex flex-col sm:items-end gap-1 text-xs opacity-80 font-medium">
            <div className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5" />
              <span>{trainResult.recordsProcessed} registros procesados · Modelo {trainResult.version}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              <span>Última ejecución: {trainResult.trainedAt}</span>
            </div>
          </div>
        </div>
      )}

      <div className={`grid grid-cols-1 lg:grid-cols-3 gap-6 transition-opacity ${loadingData ? 'opacity-50' : 'opacity-100'}`}>
        <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-600" />
              <h2 className="font-semibold text-slate-800">Rotación K-Means (RFM_05)</h2>
            </div>
            <span className="text-xs font-medium text-slate-400">Bodega #{warehouseId}</span>
          </div>
          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2">Producto</th>
                  <th className="p-2">Cluster</th>
                  <th className="p-2">Rotación</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {segmentation.map((item) => (
                  <tr key={item.id}>
                    <td className="p-2">
                      <div className="font-medium text-slate-800">{getProductName(item.product_id)}</div>
                      <div className="text-[11px] text-slate-400">ID #{item.product_id}</div>
                    </td>
                    <td className="p-2">{item.cluster_group}</td>
                    <td className="p-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        item.rotation_type === 'Alta' ? 'bg-green-100 text-green-800' :
                        item.rotation_type === 'Media' ? 'bg-blue-100 text-blue-800' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {item.rotation_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
              <h2 className="font-semibold text-slate-800">Demanda Estimada (RFM_06)</h2>
            </div>
            <span className="text-xs font-medium text-slate-400">Bodega #{warehouseId}</span>
          </div>
          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2">Producto</th>
                  <th className="p-2">Demanda 30d</th>
                  <th className="p-2">Modelo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {predictions.map((pred) => (
                  <tr key={pred.id}>
                    <td className="p-2">
                      <div className="font-medium text-slate-800">{getProductName(pred.product_id)}</div>
                      <div className="text-[11px] text-slate-400">ID #{pred.product_id}</div>
                    </td>
                    <td className="p-2 font-bold text-emerald-700">{Math.round(pred.predicted_demand)} uds</td>
                    <td className="p-2 text-xs text-slate-400">
                      {pred.model_version || (pred.model_id ? `v${pred.model_id}` : 'RF-v1')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <PackageCheck className="w-5 h-5 text-amber-600" />
              <h2 className="font-semibold text-slate-800">Stock Sugerido (RFM_07)</h2>
            </div>
            <span className="text-xs font-medium text-slate-400">Bodega #{warehouseId}</span>
          </div>
          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2">Producto</th>
                  <th className="p-2">Óptimo Sugerido</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {suggestions.map((sug) => {
                  const qty = sug.suggested_stock ?? sug.optimal_stock ?? sug.recommended_stock ?? sug.suggested_quantity ?? 0;
                  return (
                    <tr key={sug.id}>
                      <td className="p-2">
                        <div className="font-medium text-slate-800">{getProductName(sug.product_id)}</div>
                        <div className="text-[11px] text-slate-400">ID #{sug.product_id}</div>
                      </td>
                      <td className="p-2 font-bold text-amber-700">{Math.round(qty)} uds</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}