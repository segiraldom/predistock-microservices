const validateLoginBody = (req, res, next) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'Debe ingresar email y contraseña.' });
  }
  next();
};

const validateUserCreation = (req, res, next) => {
  const { nombre, apellido, email, password, rol_id } = req.body;
  if (!nombre || !apellido || !email || !password || !rol_id) {
    return res.status(400).json({ 
      error: 'Campos obligatorios faltantes: nombre, apellido, email, password y rol_id.' 
    });
  }
  next();
};

module.exports = {
  validateLoginBody,
  validateUserCreation,
};