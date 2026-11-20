import { useState, useEffect } from 'react';
import gatewayClient from '../api/gatewayClient';
import ServiceStatusCard from '../components/ServiceStatusCard';
import { useAuth } from '../context/AuthContext';

export default function CatalogPage() {
  const { hasRole } = useAuth();
  const [products, setProducts] = useState([]);
  const [offline, setOffline] = useState(false);

  const loadProducts = async () => {
    setOffline(false);
    try {
      const { data } = await gatewayClient.get('/catalogo/productos');
      setProducts(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      if (err.isServiceOffline) setOffline(true);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  if (offline) {
    return <ServiceStatusCard serviceName="ms-catalogo (Django)" port="8001" onRetry={loadProducts} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-800">Catálogo de Productos y Proveedores</h1>
        {hasRole('ADMIN') && (
          <button className="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium cursor-pointer">
            + Nuevo Producto
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="p-3">SKU / ID</th>
              <th className="p-3">Producto</th>
              <th className="p-3">Categoría</th>
              <th className="p-3">Proveedor</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {products.map((p) => (
              <tr key={p.id}>
                <td className="p-3">{p.sku || p.id}</td>
                <td className="p-3 font-medium">{p.nombre}</td>
                <td className="p-3">{p.categoria}</td>
                <td className="p-3">{p.proveedor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}