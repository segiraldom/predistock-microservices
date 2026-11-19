/** Formato de error uniforme de PrediStock: {"error": CODIGO, "mensaje": texto}. */

const metodoNoPermitido = (req, res) => {
  res.status(405).json({
    error: 'METODO_NO_PERMITIDO',
    mensaje: `El método ${req.method} no está permitido en esta ruta.`,
  });
};

const rutaNoEncontrada = (req, res) => {
  res.status(404).json({
    error: 'NO_ENCONTRADO',
    mensaje: 'La ruta no existe en ms-notificaciones.',
  });
};

// eslint-disable-next-line no-unused-vars
const manejadorErrores = (err, req, res, next) => {
  // JSON malformado (lo detecta express.json)
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'DATOS_INVALIDOS', mensaje: 'El cuerpo no es un JSON válido.' });
  }
  if (err.type === 'entity.too.large') {
    return res.status(413).json({ error: 'DEMASIADO_GRANDE', mensaje: 'El cuerpo de la petición es demasiado grande.' });
  }

  console.error('[Notifications Service] Error inesperado:', err);
  return res.status(500).json({ error: 'ERROR_INTERNO', mensaje: 'Error inesperado en ms-notificaciones.' });
};

module.exports = {
  metodoNoPermitido,
  rutaNoEncontrada,
  manejadorErrores,
};
