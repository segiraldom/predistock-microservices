const express = require('express');
const alertRoutes = require('./routes/alertRoutes');
const { rutaNoEncontrada, manejadorErrores } = require('./middlewares/errores');

const app = express();

app.disable('x-powered-by');
app.use(express.json());

// Verificación de salud para Docker, Kubernetes y Gateway
app.get('/api/notifications/health', (req, res) => {
  res.json({ status: 'ok', servicio: 'ms-notificaciones' });
});

// Registro de endpoints modularizados
app.use('/api/notifications', alertRoutes);

// Errores con el formato uniforme {error, mensaje}
app.use(rutaNoEncontrada);
app.use(manejadorErrores);

const PORT = process.env.PORT || 5001;

if (process.env.NODE_ENV !== 'test') {
  const server = app.listen(PORT, () => {
    console.log(`[Notifications Service] Escuchando en el puerto ${PORT}`);
  });

  // Cierre ordenado: Docker envía SIGTERM al detener el contenedor
  const cerrar = () => server.close(() => process.exit(0));
  process.on('SIGTERM', cerrar);
  process.on('SIGINT', cerrar);
}

module.exports = app;
