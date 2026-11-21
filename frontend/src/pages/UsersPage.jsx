import { useState, useEffect } from 'react';
import { UserPlus } from 'lucide-react';
import gatewayClient from '../api/gatewayClient';

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [form, setForm] = useState({ nombre: '', apellido: '', email: '', password: '', rol_id: 2, bodega_id: 1 });
  const [msg, setMsg] = useState('');

  const loadData = async () => {
    try {
      const [uRes, rRes] = await Promise.all([
        gatewayClient.get('/usuarios/usuarios'),
        gatewayClient.get('/usuarios/roles'),
      ]);
      const usersList = Array.isArray(uRes.data) ? uRes.data : (uRes.data.usuarios || uRes.data.users || []);
      const rolesList = Array.isArray(rRes.data) ? rRes.data : (rRes.data.roles || []);
      setUsers(usersList);
      setRoles(rolesList);
    } catch (err) {
      setMsg(err.response?.data?.error || err.friendlyMessage || 'Error cargando usuarios.');
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setMsg('');
    try {
      await gatewayClient.post('/usuarios/usuarios', {
        ...form,
        rol_id: Number(form.rol_id),
        bodega_id: form.bodega_id ? Number(form.bodega_id) : null,
      });
      setMsg('Usuario creado correctamente.');
      setForm({ nombre: '', apellido: '', email: '', password: '', rol_id: 2, bodega_id: 1 });
      loadData();
    } catch (err) {
      setMsg(err.response?.data?.error || 'Error creando usuario');
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Gestión de Usuarios y Roles (RBAC)</h1>

      <form onSubmit={handleCreate} className="bg-white p-5 rounded-lg shadow-sm border border-slate-200 grid grid-cols-1 md:grid-cols-3 gap-4">
        <input placeholder="Nombre" required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} className="border border-slate-300 p-2 rounded text-sm" />
        <input placeholder="Apellido" required value={form.apellido} onChange={(e) => setForm({ ...form, apellido: e.target.value })} className="border border-slate-300 p-2 rounded text-sm" />
        <input type="email" placeholder="Correo electrónico" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border border-slate-300 p-2 rounded text-sm" />
        <input type="password" placeholder="Contraseña" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="border border-slate-300 p-2 rounded text-sm" />
        <select value={form.rol_id} onChange={(e) => setForm({ ...form, rol_id: e.target.value })} className="border border-slate-300 p-2 rounded text-sm">
          {roles.map((r) => (
            <option key={r.id} value={r.id}>{r.nombre}</option>
          ))}
        </select>
        <button type="submit" className="flex items-center justify-center gap-2 bg-slate-900 text-white rounded p-2 text-sm font-medium hover:bg-slate-800 cursor-pointer">
          <UserPlus className="w-4 h-4" /> Registrar Usuario
        </button>
      </form>

      {msg && <p className="text-sm text-indigo-600 font-medium">{msg}</p>}

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="p-3">ID</th>
              <th className="p-3">Nombre</th>
              <th className="p-3">Email</th>
              <th className="p-3">Rol</th>
              <th className="p-3">Bodega</th>
              <th className="p-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="p-3">{u.id}</td>
                <td className="p-3 font-medium">{u.nombre} {u.apellido}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3">
                  <span className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-xs font-semibold">
                    {u.rol || u.rol_nombre}
                  </span>
                </td>
                <td className="p-3">{u.bodega_id ?? 'Global'}</td>
                <td className="p-3">{u.activo ? 'Activo' : 'Inactivo'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}