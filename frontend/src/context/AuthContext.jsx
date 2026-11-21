import { createContext, useContext, useState, useEffect } from 'react';
import gatewayClient from '../api/gatewayClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('predistock_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const verifySession = async () => {
      const token = localStorage.getItem('predistock_token');
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const { data } = await gatewayClient.get('/auth/me');
        setUser(data);
        localStorage.setItem('predistock_user', JSON.stringify(data));
      } catch {
        localStorage.removeItem('predistock_token');
        localStorage.removeItem('predistock_user');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    verifySession();
  }, []);

  const login = async (email, password) => {
    const { data } = await gatewayClient.post('/usuarios/auth/login', { email, password });
    localStorage.setItem('predistock_token', data.token);
    localStorage.setItem('predistock_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await gatewayClient.post('/auth/logout');
    } catch {
      // JWT stateless
    } finally {
      localStorage.removeItem('predistock_token');
      localStorage.removeItem('predistock_user');
      setUser(null);
    }
  };

  const hasRole = (...allowedRoles) => {
    if (!user?.rol) return false;
    return allowedRoles.includes(user.rol);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, hasRole, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);