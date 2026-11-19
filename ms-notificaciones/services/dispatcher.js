/**
 * Despacho de alertas (RF09).
 *
 * El servicio no tiene base de datos ni cola: la alerta se registra como una línea JSON
 * en la salida estándar (visible con `docker compose logs ms-notificaciones`) y se
 * responde como entregada. Un canal real (SSE, WebSocket, correo) se conectaría aquí,
 * sin cambiar la ruta ni el controlador.
 */
const CANAL = 'realtime_push';

const despachar = (alerta) => {
  const timestamp = new Date().toISOString();

  console.log(JSON.stringify({
    evento: 'ALERTA_DESPACHADA',
    canal: CANAL,
    timestamp,
    ...alerta,
  }));

  return { status: 'delivered', channel: CANAL, timestamp };
};

module.exports = {
  CANAL,
  despachar,
};
