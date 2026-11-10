const bcrypt = require('bcryptjs');
const { pool } = require('../config/db');

// RF07: Listar roles del sistema
const listRoles = async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM roles ORDER BY id ASC');
    return res.json(result.rows);
  } catch (err) {
    return res.status(500).json({ error: 'Error al consultar roles: ' + err.message });
  }
};

// RF07: Listar todos los usuarios
const listUsers = async (req, res) => {
  try {
    const query = `
      SELECT u.id, u.nombre, u.apellido, u.email, u.rol_id, r.nombre AS rol, u.bodega_id, u.activo, u.created_at
      FROM usuarios u
      LEFT JOIN roles r ON u.rol_id = r.id
      ORDER BY u.id ASC
    `;
    const result = await pool.query(query);
    return res.json(result.rows);
  } catch (err) {
    return res.status(500).json({ error: 'Error al listar usuarios: ' + err.message });
  }
};

// RF07: Crear usuario nuevo
const createUser = async (req, res) => {
  const { nombre, apellido, email, password, rol_id, bodega_id } = req.body;
  const cleanEmail = email.toLowerCase().trim();

  try {
    const existing = await pool.query('SELECT id FROM usuarios WHERE email = $1', [cleanEmail]);
    if (existing.rows.length > 0) {
      return res.status(400).json({ error: 'El correo electrónico ya se encuentra registrado.' });
    }

    const passwordHash = bcrypt.hashSync(password, 10);
    const insertQuery = `
      INSERT INTO usuarios (nombre, apellido, email, password_hash, rol_id, bodega_id, activo)
      VALUES ($1, $2, $3, $4, $5, $6, true)
      RETURNING id, nombre, apellido, email, rol_id, bodega_id, activo, created_at
    `;
    const result = await pool.query(insertQuery, [
      nombre.trim(),
      apellido.trim(),
      cleanEmail,
      passwordHash,
      parseInt(rol_id),
      bodega_id ? parseInt(bodega_id) : null
    ]);

    return res.status(201).json(result.rows[0]);
  } catch (err) {
    return res.status(500).json({ error: 'Error creando usuario: ' + err.message });
  }
};

// RF07: Actualizar datos de usuario
const updateUser = async (req, res) => {
  const { id } = req.params;
  const { nombre, apellido, rol_id, bodega_id, activo } = req.body;

  try {
    const updateQuery = `
      UPDATE usuarios 
      SET nombre = COALESCE($1, nombre),
          apellido = COALESCE($2, apellido),
          rol_id = COALESCE($3, rol_id),
          bodega_id = COALESCE($4, bodega_id),
          activo = COALESCE($5, activo),
          updated_at = NOW()
      WHERE id = $6
      RETURNING id, nombre, apellido, email, rol_id, bodega_id, activo, updated_at
    `;
    const result = await pool.query(updateQuery, [
      nombre ? nombre.trim() : null,
      apellido ? apellido.trim() : null,
      rol_id ? parseInt(rol_id) : null,
      bodega_id !== undefined ? (bodega_id ? parseInt(bodega_id) : null) : null,
      activo !== undefined ? activo : null,
      id
    ]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado.' });
    }

    return res.json(result.rows[0]);
  } catch (err) {
    return res.status(500).json({ error: 'Error actualizando usuario: ' + err.message });
  }
};

module.exports = {
  listRoles,
  listUsers,
  createUser,
  updateUser,
};