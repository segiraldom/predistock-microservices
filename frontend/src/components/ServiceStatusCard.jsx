import { ServerOff, RefreshCw } from 'lucide-react';

export default function ServiceStatusCard({ serviceName, port, onRetry }) {
  return (
    <div className="border border-amber-300 bg-amber-50 rounded-lg p-6 text-amber-900 flex items-center justify-between gap-4">
      <div className="flex items-start gap-4">
        <ServerOff className="w-8 h-8 text-amber-600 shrink-0 mt-1" />
        <div>
          <h3 className="font-semibold text-lg">
            Microservicio <code className="bg-amber-100 px-1.5 py-0.5 rounded">{serviceName}</code> no disponible
          </h3>
          <p className="text-sm text-amber-800 mt-1">
            El API Gateway respondió <strong>503 Service Unavailable</strong> al intentar enrutar hacia el puerto interno <strong>{port}</strong>. 
            En cuanto el contenedor esté activo en Docker Compose, este módulo cargará automáticamente.
          </p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 text-sm font-medium shrink-0 cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" /> Reintentar
        </button>
      )}
    </div>
  );
}