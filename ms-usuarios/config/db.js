const { Pool } = require('pg');

const DATABASE_URL = process.env.DATABASE_URL || 'postgresql://predi_user:predi_password@autentificacion-db:5432/autentificacion_db';

const pool = new Pool({
  connectionString: DATABASE_URL,
});

// Inicialización de las tablas relacionales y registros semilla
const initDb = async () => {
  const queryDDL = `
    CREATE TABLE IF NOT EXISTS roles (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(30) UNIQUE NOT NULL,
        descripcion VARCHAR(255)
    );

    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        apellido VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        rol_id INT REFERENCES roles(id),
        bodega_id INT NULL,
        activo BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tokens_recuperacion (
        id SERIAL PRIMARY KEY,
        usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
        token_hash VARCHAR(255) NOT NULL,
        expira_en TIMESTAMP NOT NULL,
        usado BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `;

  try {
    await pool.query(queryDDL);

    // Precarga de roles base para PrediStock (RF07)
    await pool.query(`
      INSERT INTO roles (id, nombre, descripcion) VALUES
      (1, 'Administrador', 'Control total de la plataforma y analítica'),
      (2, 'Operador de Bodega', 'Gestión de existencias y pedidos')
      ON CONFLICT (id) DO NOTHING;
    `);

    // Precarga de usuario administrador inicial
    const bcrypt = require('bcryptjs');
    const adminPassHash = bcrypt.hashSync('Admin2026*', 10);
    await pool.query(`
      INSERT INTO usuarios (nombre, apellido, email, password_hash, rol_id, bodega_id, activo)
      VALUES ('Cristian', 'Bedoya', 'admin@predistock.com', $1, 1, 1, true)
      ON CONFLICT (email) DO NOTHING;
    `, [adminPassHash]);

    console.log('[Users Service] Tablas relacionales inicializadas correctamente en autentificacion_db.');
  } catch (err) {
    console.error('[Users Service] Error al inicializar esquema en PostgreSQL:', err.message);
  }
};

module.exports = {
  pool,
  initDb,
};