import axios from 'axios';

const gatewayClient = axios.create({
  baseURL: import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

gatewayClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('predistock_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

gatewayClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if (status === 401) {
      localStorage.removeItem('predistock_token');
      localStorage.removeItem('predistock_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    if (status === 503) {
      error.isServiceOffline = true;
      error.friendlyMessage = 'El microservicio destino aún no está desplegado en el clúster (503).';
    }

    if (status === 403) {
      error.friendlyMessage = 'Tu rol no tiene permisos para ejecutar esta acción (403).';
    }

    return Promise.reject(error);
  }
);

export default gatewayClient;