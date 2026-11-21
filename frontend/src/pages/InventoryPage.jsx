import { useState, useEffect } from 'react';
import gatewayClient from '../api/gatewayClient';
import ServiceStatusCard from '../components/ServiceStatusCard';
import { useAuth } from '../context/AuthContext';

export default function InventoryPage() {
  const { hasRole } = useAuth();
  const [stock, setStock] = useState([]);
  const [offline, setOffline] = useState(false);

  const loadStock = async () => {
    setOffline(false);
    try {
      const { data } = await gatewayClient.get('/existencias/stock');
      setStock(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      if (err.isServiceOffline) setOffline(true);
    }
  };

  useEffect(() => {
    loadStock();
  }, []);

  if (offline) {
    return <ServiceStatusCard serviceName="ms-existencias (Django)" port="8002" onRetry={loadStock} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-800">Control de Existencias por Bodega</h1>
        {hasRole('ADMIN', 'OPERADOR_BODEGA') && (
          <div className="flex gap-2">
            <button className="bg-emerald-600 text-white px-3 py-2 rounded-md text-sm cursor-pointer">Registrar Movimiento</button>
            <button className="bg-slate-800 text-white px-3 py-2 rounded-md text-sm cursor-pointer">Nuevo Traslado</button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="p-3">Bodega</th>
              <th className="p-3">Producto ID</th>
              <th className="p-3">Cantidad Disponible</th>
              <th className="p-3">Stock Mínimo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {stock.map((item) => (
              <tr key={item.id}>
                <td className="p-3">Bodega #{item.bodega_id}</td>
                <td className="p-3">#{item.producto_id}</td>
                <td className="p-3 font-bold">{item.cantidad}</td>
                <td className="p-3 text-slate-500">{item.stock_minimo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}