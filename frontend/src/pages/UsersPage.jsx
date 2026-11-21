import { useState, useEffect } from 'react';
import { UserPlus, AlertCircle, CheckCircle2 } from 'lucide-react';
import gatewayClient from '../api/gatewayClient';

const BODEGAS = [
  { id: '', label: 'Global (Todas las bodegas)' },
  { id: '1', label: '1 - Bodega Central' },
  { id: '2', label: '2 - Bodega Norte' },
  { id: '3', label: '3 - Bodega Sur' },
];

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', text: '' });

  const [form, setForm] = useState({
    nombre: '',
    apellido: '',
    email: '',
    password: '',
    rol_id: '2',
    bodega_id: '1',
  });

  const fetchUsersAndRoles = async () => {
    setLoading(true);
    try {
      const [usersRes, rolesRes] = await Promise.all([
        gatewayClient.get('/usuarios/usuarios'),
        gatewayClient.get('/usuarios/roles'),
      ]);
      setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
      setRoles(Array.isArray(rolesRes.data) ? rolesRes.data : []);
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.response?.data?.error || 'Error cargando usuarios y roles.',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsersAndRoles();
  }, []);

  const handleRoleChange = (newRolId) => {
    // Si es ADMIN (1) o ANALISTA (3), sugiere Global por defecto; si es OPERADOR (2), Bodega 1
    const defaultBodega = newRolId === '2' ? '1' : '';
    setForm({ ...form, rol_id: newRolId, bodega_id: defaultBodega });
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setFeedback({ type: '', text: '' });
    try {
      await gatewayClient.post('/usuarios/usuarios', {
        ...form,
        rol_id: Number(form.rol_id),
        bodega_id: form.bodega_id === '' ? null : Number(form.bodega_id),
      });
      setFeedback({ type: 'success', text: 'Usuario creado correctamente.' });
      setForm({ nombre: '', apellido: '', email: '', password: '', rol_id: '2', bodega_id: '1' });
      await fetchUsersAndRoles();
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.response?.data?.error || 'No se pudo registrar el usuario.',
      });
    }
  };

  const handleUpdateWarehouse = async (userId, newBodegaValue) => {
    setFeedback({ type: '', text: '' });
    try {
      await gatewayClient.put(`/usuarios/usuarios/${userId}`, {
        bodega_id: newBodegaValue === '' ? null : Number(newBodegaValue),
      });
      setFeedback({ type: 'success', text: `Bodega actualizada para el usuario #${userId}.` });
      await fetchUsersAndRoles();
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.response?.data?.error || 'Error al actualizar la bodega.',
      });
    }
  };

  const handleToggleActive = async (user) => {
    setFeedback({ type: '', text: '' });
    try {
      await gatewayClient.put(`/usuarios/usuarios/${user.id}`, {
        activo: !user.activo,
      });
      await fetchUsersAndRoles();
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.response?.data?.error || 'Error al cambiar el estado del usuario.',
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-200">
        <h1 className="text-2xl font-bold text-slate-800 mb-4">Gestión de Usuarios y Roles (RBAC)</h1>

        <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            placeholder="Nombre"
            required
            value={form.nombre}
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Apellido"
            required
            value={form.apellido}
            onChange={(e) => setForm({ ...form, apellido: e.target.value })}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
          <input
            type="email"
            placeholder="Correo electrónico"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
          <input
            type="password"
            placeholder="Contraseña"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
          <select
            value={form.rol_id}
            onChange={(e) => handleRoleChange(e.target.value)}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
          >
            {roles.length > 0 ? (
              roles.map((r) => (
                <option key={r.id} value={r.id}>{r.nombre}</option>
              ))
            ) : (
              <>
                <option value="1">ADMIN</option>
                <option value="2">OPERADOR_BODEGA</option>
                <option value="3">ANALISTA</option>
              </>
            )}
          </select>
          <select
            value={form.bodega_id}
            onChange={(e) => setForm({ ...form, bodega_id: e.target.value })}
            className="border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
          >
            {BODEGAS.map((b) => (
              <option key={b.id} value={b.id}>{b.label}</option>
            ))}
          </select>

          <div className="md:col-span-3 flex justify-end">
            <button
              type="submit"
              className="flex items-center justify-center gap-2 bg-slate-900 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-slate-800 cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              Registrar Usuario
            </button>
          </div>
        </form>

        {feedback.text && (
          <div className={`mt-4 flex items-center gap-2 text-sm ${
            feedback.type === 'success' ? 'text-indigo-600' : 'text-red-600'
          }`}>
            {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{feedback.text}</span>
          </div>
        )}
      </div>

      <div className={`bg-white rounded-lg shadow-sm border border-slate-200 overflow-x-auto ${loading ? 'opacity-60' : ''}`}>
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
            <tr>
              <th className="p-3.5">ID</th>
              <th className="p-3.5">Nombre</th>
              <th className="p-3.5">Email</th>
              <th className="p-3.5">Rol</th>
              <th className="p-3.5">Bodega</th>
              <th className="p-3.5">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="p-3.5 text-slate-500">{u.id}</td>
                <td className="p-3.5 font-medium text-slate-800">{u.nombre} {u.apellido}</td>
                <td className="p-3.5 text-slate-600">{u.email}</td>
                <td className="p-3.5">
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700">
                    {u.rol}
                  </span>
                </td>
                <td className="p-3.5">
                  <select
                    value={u.bodega_id ?? ''}
                    onChange={(e) => handleUpdateWarehouse(u.id, e.target.value)}
                    className="border border-slate-200 rounded px-2 py-1 text-xs bg-slate-50 text-slate-700 hover:border-slate-300 cursor-pointer"
                  >
                    {BODEGAS.map((b) => (
                      <option key={b.id} value={b.id}>{b.label}</option>
                    ))}
                  </select>
                </td>
                <td className="p-3.5">
                  <button
                    type="button"
                    onClick={() => handleToggleActive(u)}
                    className={`text-xs font-medium px-2 py-0.5 rounded cursor-pointer ${
                      u.activo ? 'text-emerald-700 bg-emerald-50' : 'text-slate-500 bg-slate-100'
                    }`}
                  >
                    {u.activo ? 'Activo' : 'Inactivo'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}