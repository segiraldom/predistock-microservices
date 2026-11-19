/**
 * Validación del cuerpo StockAlertPayload del contrato.
 *
 * current_stock y threshold aceptan decimales: ms-existencias los envía como float
 * cuando la cantidad no es entera (p. ej. productos a granel).
 */
const CAMPOS = ['alert_type', 'product_id', 'warehouse_id', 'current_stock', 'threshold', 'message'];

const esTexto = (v) => typeof v === 'string' && v.trim() !== '';
const esIdPositivo = (v) => Number.isInteger(v) && v > 0;
const esCantidad = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;

const REGLAS = {
  alert_type: [esTexto, 'Debe ser un texto no vacío.'],
  product_id: [esIdPositivo, 'Debe ser un entero positivo.'],
  warehouse_id: [esIdPositivo, 'Debe ser un entero positivo.'],
  current_stock: [esCantidad, 'Debe ser un número mayor o igual a 0.'],
  threshold: [esCantidad, 'Debe ser un número mayor o igual a 0.'],
  message: [esTexto, 'Debe ser un texto no vacío.'],
};

const exigirJson = (req, res, next) => {
  if (!req.is('application/json')) {
    return res.status(415).json({
      error: 'TIPO_NO_SOPORTADO',
      mensaje: 'El cuerpo debe enviarse como application/json.',
    });
  }
  next();
};

const validateAlertBody = (req, res, next) => {
  const body = req.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return res.status(400).json({
      error: 'DATOS_INVALIDOS',
      mensaje: 'El cuerpo debe ser un objeto JSON con los datos de la alerta.',
    });
  }

  // Errores campo por campo, como los servicios Django: {campo: [texto]}
  const errores = {};
  for (const campo of CAMPOS) {
    const [esValido, texto] = REGLAS[campo];
    if (body[campo] === undefined || body[campo] === null) {
      errores[campo] = ['Este campo es obligatorio.'];
    } else if (!esValido(body[campo])) {
      errores[campo] = [texto];
    }
  }
  if (Object.keys(errores).length > 0) {
    return res.status(400).json({ error: 'DATOS_INVALIDOS', mensaje: errores });
  }

  // Solo se despachan los campos del contrato
  req.alerta = {
    alert_type: body.alert_type.trim(),
    product_id: body.product_id,
    warehouse_id: body.warehouse_id,
    current_stock: body.current_stock,
    threshold: body.threshold,
    message: body.message.trim(),
  };
  next();
};

module.exports = {
  exigirJson,
  validateAlertBody,
};
