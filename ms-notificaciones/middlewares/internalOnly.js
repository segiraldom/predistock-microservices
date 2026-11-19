/**
 * El endpoint de alertas es de uso interno: ms-existencias lo llama directamente por la
 * red de Docker, sin cabeceras de identidad. Toda petición que pasa por el API Gateway
 * llega con X-Usuario-Id / X-Rol (las agrega tras validar el JWT), así que se rechaza:
 * un usuario no puede fabricar alertas.
 */
const CABECERAS_GATEWAY = ['x-usuario-id', 'x-rol'];

const soloRedInterna = (req, res, next) => {
  if (CABECERAS_GATEWAY.some((h) => req.get(h) !== undefined)) {
    return res.status(403).json({
      error: 'SIN_PERMISO',
      mensaje: 'Las alertas solo pueden enviarse desde los microservicios internos.',
    });
  }
  next();
};

module.exports = {
  soloRedInterna,
};
