const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { pool } = require('../config/db');

const JWT_SECRET = process.env.JWT_SECRET || 'password_2026';

// RF08: Login
const login = async (req, res) => {
  const { email, password } = req.body;
  const cleanEmail = email.toLowerCase().trim();

  try {
    const query = `
      SELECT u.*, r.nombre AS rol_nombre 
      FROM usuarios u
      LEFT JOIN roles r ON u.rol_id = r.id
      WHERE u.email = $1 AND u.activo = true
    `;
    const result = await pool.query(query, [cleanEmail]);
    const user = result.rows[0];

    if (!user || !bcrypt.compareSync(password, user.password_hash)) {
      return res.status(401).json({ error: 'Credenciales inválidas.' });
    }

    // Payload con rol y bodega para inyección en el Gateway
    const tokenPayload = {
      sub: user.id,
      email: user.email,
      nombre: `${user.nombre} ${user.apellido}`,
      rol: user.rol_nombre,
      rol_id: user.rol_id,
      bodega_id: user.bodega_id
    };

    const token = jwt.sign(tokenPayload, JWT_SECRET, { expiresIn: '12h' });

    return res.json({
      message: 'Inicio de sesión exitoso.',
      token,
      user: {
        id: user.id,
        nombre: user.nombre,
        apellido: user.apellido,
        email: user.email,
        rol: user.rol_nombre,
        bodega_id: user.bodega_id
      }
    });
  } catch (err) {
    return res.status(500).json({ error: 'Error interno en autenticación: ' + err.message });
  }
};

// RF08: Perfil del usuario activo (aprovecha la cabecera X-User-Id enviada por el Gateway)
const getProfile = async (req, res) => {
  const userId = req.headers['x-user-id'];

  if (!userId) {
    return res.status(401).json({ error: 'Contexto de usuario no proporcionado.' });
  }

  try {
    const query = `
      SELECT u.id, u.nombre, u.apellido, u.email, u.bodega_id, u.activo, r.nombre AS rol
      FROM usuarios u
      LEFT JOIN roles r ON u.rol_id = r.id
      WHERE u.id = $1
    `;
    const result = await pool.query(query, [userId]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado.' });
    }

    return res.json(result.rows[0]);
  } catch (err) {
    return res.status(500).json({ error: 'Error consultando perfil: ' + err.message });
  }
};

// RF08: Solicitar recuperación de contraseña (generación de token temporal)
const forgotPassword = async (req, res) => {
  const { email } = req.body;
  if (!email) {
    return res.status(400).json({ error: 'Debe ingresar un correo electrónico.' });
  }

  try {
    const userRes = await pool.query(
      'SELECT id FROM usuarios WHERE email = $1 AND activo = true',
      [email.toLowerCase().trim()]
    );

    if (userRes.rows.length === 0) {
      // Mensaje genérico por seguridad
      return res.json({ message: 'Si el correo está registrado, se enviará el token de restablecimiento.' });
    }

    const userId = userRes.rows[0].id;
    const rawToken = crypto.randomBytes(32).toString('hex');
    const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hora de validez

    await pool.query(
      'INSERT INTO tokens_recuperacion (usuario_id, token_hash, expira_en) VALUES ($1, $2, $3)',
      [userId, tokenHash, expiresAt]
    );

    return res.json({
      message: 'Token de recuperación generado.',
      reset_token: rawToken // Devuelto directamente para pruebas locales
    });
  } catch (err) {
    return res.status(500).json({ error: 'Error en recuperación: ' + err.message });
  }
};

// RF08: Restablecer contraseña con token
const resetPassword = async (req, res) => {
  const { token, new_password } = req.body;
  if (!token || !new_password) {
    return res.status(400).json({ error: 'Token y nueva contraseña obligatorios.' });
  }

  try {
    const tokenHash = crypto.createHash('sha256').update(token).digest('hex');
    const query = `
      SELECT * FROM tokens_recuperacion 
      WHERE token_hash = $1 AND usado = false AND expira_en > NOW()
      ORDER BY created_at DESC LIMIT 1
    `;
    const tokenRes = await pool.query(query, [tokenHash]);

    if (tokenRes.rows.length === 0) {
      return res.status(400).json({ error: 'El token es inválido o ha expirado.' });
    }

    const tokenRecord = tokenRes.rows[0];
    const passwordHash = bcrypt.hashSync(new_password, 10);

    await pool.query(
      'UPDATE usuarios SET password_hash = $1, updated_at = NOW() WHERE id = $2',
      [passwordHash, tokenRecord.usuario_id]
    );

    await pool.query(
      'UPDATE tokens_recuperacion SET usado = true WHERE id = $1',
      [tokenRecord.id]
    );

    return res.json({ message: 'Contraseña restablecida exitosamente.' });
  } catch (err) {
    return res.status(500).json({ error: 'Error restableciendo credenciales: ' + err.message });
  }
};

// RF08: Cambio de contraseña para usuario autenticado
const changePassword = async (req, res) => {
  const userId = req.headers['x-user-id'];
  const { current_password, new_password } = req.body;

  if (!userId) {
    return res.status(401).json({ error: 'No autorizado.' });
  }
  if (!current_password || !new_password) {
    return res.status(400).json({ error: 'Campos incompletos.' });
  }

  try {
    const userRes = await pool.query('SELECT password_hash FROM usuarios WHERE id = $1', [userId]);
    if (userRes.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado.' });
    }

    if (!bcrypt.compareSync(current_password, userRes.rows[0].password_hash)) {
      return res.status(400).json({ error: 'La contraseña actual no es correcta.' });
    }

    const newHash = bcrypt.hashSync(new_password, 10);
    await pool.query('UPDATE usuarios SET password_hash = $1, updated_at = NOW() WHERE id = $2', [newHash, userId]);

    return res.json({ message: 'Contraseña actualizada correctamente.' });
  } catch (err) {
    return res.status(500).json({ error: 'Error cambiando contraseña: ' + err.message });
  }
};

module.exports = {
  login,
  getProfile,
  forgotPassword,
  resetPassword,
  changePassword,
};