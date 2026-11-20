import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Bell, LogOut } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import gatewayClient from './api/gatewayClient';
import Login from './pages/Login';
import AnalyticsPage from './pages/AnalyticsPage';
import UsersPage from './pages/UsersPage';
import CatalogPage from './pages/CatalogPage';
import InventoryPage from './pages/InventoryPage';

function DashboardShell() {
  const { user, logout, hasRole, loading } = useAuth();
  const [alertsCount, setAlertsCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    // Consulta silenciosa a ms-notificaciones:5001 (degrada sin error si aún no está levantado)
    gatewayClient.get('/notifications')
      .then((res) => {
        const items = Array.isArray(res.data) ? res.data : [];
        setAlertsCount(items.length);
      })
      .catch(() => setAlertsCount(0));
  }, [user]);

  if (loading) return <div className="p-8 text-slate-600">Validando sesión...</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen flex bg-slate-100">
      <aside className="w-64 bg-slate-900 text-white flex flex-col justify-between p-4 shrink-0">
        <div>
          <div className="mb-8 px-2 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold tracking-tight">PrediStock</h2>
              <span className="text-xs text-slate-400">Rol: {user.rol}</span>
            </div>
            <div className="relative p-1.5 bg-slate-800 rounded-lg" title="Alertas de Stock">
              <Bell className="w-4 h-4 text-slate-300" />
              {alertsCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold px-1.5 rounded-full">
                  {alertsCount}
                </span>
              )}
            </div>
          </div>

          <nav className="space-y-1 text-sm">
            {hasRole('ADMIN', 'ANALISTA') && (
              <Link to="/analytics" className="block px-3 py-2 rounded hover:bg-slate-800">Analítica y ML</Link>
            )}
            <Link to="/catalogo" className="block px-3 py-2 rounded hover:bg-slate-800">Catálogo</Link>
            <Link to="/existencias" className="block px-3 py-2 rounded hover:bg-slate-800">Existencias</Link>
            {hasRole('ADMIN') && (
              <Link to="/usuarios" className="block px-3 py-2 rounded hover:bg-slate-800">Usuarios y Roles</Link>
            )}
          </nav>
        </div>

        <button
          onClick={logout}
          className="flex items-center gap-2 w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-slate-800 rounded cursor-pointer"
        >
          <LogOut className="w-4 h-4" /> Cerrar sesión
        </button>
      </aside>

      <main className="flex-1 p-8 overflow-y-auto">
        <Routes>
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/catalogo" element={<CatalogPage />} />
          <Route path="/existencias" element={<InventoryPage />} />
          <Route path="/usuarios" element={<UsersPage />} />
          <Route path="*" element={<Navigate to={hasRole('OPERADOR_BODEGA') ? '/existencias' : '/analytics'} replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<DashboardShell />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}