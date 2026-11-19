const dispatcher = require('../services/dispatcher');

// RF09: despacha la alerta de stock bajo a los destinatarios
const despacharAlerta = (req, res, next) => {
  try {
    const resultado = dispatcher.despachar(req.alerta);
    return res.status(200).json(resultado);
  } catch (err) {
    return next(err);
  }
};

module.exports = {
  despacharAlerta,
};
