const express = require('express');
const cors = require('cors');
const { initDb } = require('./config/db');
const { runSeeder } = require('./seed');
const authRoutes = require('./routes/authRoutes');
const userRoutes = require('./routes/userRoutes');

const app = express();

app.use(cors());
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ service: 'users-service', status: 'UP' });
});

app.use('/auth', authRoutes);
app.use('/api/usuarios/auth', authRoutes);
app.use('/api/usuarios', userRoutes);

const PORT = process.env.PORT || 3000;

if (process.env.NODE_ENV !== 'test') {
  initDb()
    .then(() => {
      app.listen(PORT, () => {
        console.log(`[Users Service] Escuchando en el puerto ${PORT}`);
      });
    })
    .catch((err) => {
      console.error('Fallo crítico iniciando servidor:', err);
      process.exit(1);
    });
}

module.exports = app;