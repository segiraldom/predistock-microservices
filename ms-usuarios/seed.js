const bcrypt = require('bcryptjs');
const { pool, initDb } = require('./config/db');

const runSeeder = async () => {
  try {
    await initDb();

    // 1. Roles del sistema (RBAC)
    await pool.query(`
      INSERT INTO roles (id, nombre, descripcion) VALUES
      (1, 'ADMIN', 'Control total de la plataforma y administracion general'),
      (2, 'OPERADOR_BODEGA', 'Control de existencias, recepcion y traslados'),
      (3, 'ANALISTA', 'Consulta y ejecucion de modelos predictivos y analitica')
      ON CONFLICT (id) DO UPDATE SET
        nombre = EXCLUDED.nombre,
        descripcion = EXCLUDED.descripcion;
    `);

    // 2. Usuarios semilla para pruebas de cada rol
    const seedUsers = [
      {
        nombre: 'Cristian',
        apellido: 'Bedoya',
        email: 'admin@predistock.com',
        password: 'Admin2026*',
        rol_id: 1,
        bodega_id: 1,
      },
      {
        nombre: 'Carlos',
        apellido: 'Operador',
        email: 'operador@predistock.com',
        password: 'Operador2026*',
        rol_id: 2,
        bodega_id: 1,
      },
      {
        nombre: 'Laura',
        apellido: 'Analista',
        email: 'analista@predistock.com',
        password: 'Analista2026*',
        rol_id: 3,
        bodega_id: null,
      },
    ];

    for (const u of seedUsers) {
      const hash = bcrypt.hashSync(u.password, 10);
      await pool.query(
        `
        INSERT INTO usuarios (nombre, apellido, email, password_hash, rol_id, bodega_id, activo)
        VALUES ($1, $2, $3, $4, $5, $6, true)
        ON CONFLICT (email) DO NOTHING;
        `,
        [u.nombre, u.apellido, u.email, hash, u.rol_id, u.bodega_id]
      );
    }

    console.log('[Seeder] Roles y usuarios iniciales cargados correctamente.');
  } catch (err) {
    console.error('[Seeder] Error ejecutando seeder:', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
};

if (require.main === module) {
  runSeeder();
}

module.exports = { runSeeder };