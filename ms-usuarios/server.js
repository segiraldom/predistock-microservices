const express = require('express');
const cors = require('cors');
const { initDb } = require('./config/db');
const authRoutes = require('./routes/authRoutes');
const userRoutes = require('./routes/userRoutes');

const app = express();

app.use(cors());
app.use(express.json());

// Verificación de salud para Kubernetes y Gateway
app.get('/health', (req, res) => {
  res.json({ service: 'users-service', status: 'UP' });
});

// Registro de endpoints modularizados
app.use('/api/v1/auth', authRoutes);
app.use('/api/v1', userRoutes);

// Inicializar esquemas en la base de datos
initDb();

const PORT = process.env.PORT || 8001;

if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`[Users Service] Escuchando en el puerto ${PORT}`);
  });
}

module.exports = app;