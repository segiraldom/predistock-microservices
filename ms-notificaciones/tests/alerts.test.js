process.env.NODE_ENV = 'test';

const request = require('supertest');
const app = require('../server');

const URL = '/api/notifications/alerts';

// Mismo cuerpo que envía ms-existencias (inventario/notificaciones.py)
const alertaValida = () => ({
  alert_type: 'LOW_STOCK_THRESHOLD',
  product_id: 104,
  warehouse_id: 1,
  current_stock: 4,
  threshold: 10,
  message: 'Stock bajo: quedan 4 unidades del producto 104 en Bodega Central (mínimo 10).',
});

let logSpy;
beforeEach(() => {
  logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

describe('GET /api/notifications/health', () => {
  test('responde ok', async () => {
    const res = await request(app).get('/api/notifications/health');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok', servicio: 'ms-notificaciones' });
  });
});

describe('POST /alerts: despacho', () => {
  test('alerta válida -> 200 con DispatchResult', async () => {
    const res = await request(app).post(URL).send(alertaValida());
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('delivered');
    expect(res.body.channel).toBe('realtime_push');
    expect(new Date(res.body.timestamp).toISOString()).toBe(res.body.timestamp);
  });

  test('registra la alerta en el log como JSON', async () => {
    await request(app).post(URL).send(alertaValida());
    const lineas = logSpy.mock.calls.map(([l]) => JSON.parse(l));
    expect(lineas).toHaveLength(1);
    expect(lineas[0]).toMatchObject({
      evento: 'ALERTA_DESPACHADA',
      canal: 'realtime_push',
      alert_type: 'LOW_STOCK_THRESHOLD',
      product_id: 104,
      warehouse_id: 1,
      current_stock: 4,
      threshold: 10,
    });
  });

  test('acepta cantidades decimales (productos a granel)', async () => {
    const res = await request(app).post(URL).send({ ...alertaValida(), current_stock: 4.5, threshold: 10.25 });
    expect(res.status).toBe(200);
  });

  test('acepta stock en cero', async () => {
    const res = await request(app).post(URL).send({ ...alertaValida(), current_stock: 0 });
    expect(res.status).toBe(200);
  });

  test('ignora campos que no están en el contrato', async () => {
    await request(app).post(URL).send({ ...alertaValida(), extra: 'x' });
    const linea = JSON.parse(logSpy.mock.calls[0][0]);
    expect(linea).not.toHaveProperty('extra');
  });
});

describe('POST /alerts: validación (400)', () => {
  test.each(['alert_type', 'product_id', 'warehouse_id', 'current_stock', 'threshold', 'message'])(
    'falta %s',
    async (campo) => {
      const datos = alertaValida();
      delete datos[campo];
      const res = await request(app).post(URL).send(datos);
      expect(res.status).toBe(400);
      expect(res.body.error).toBe('DATOS_INVALIDOS');
      expect(res.body.mensaje[campo]).toEqual(['Este campo es obligatorio.']);
      expect(logSpy).not.toHaveBeenCalled();
    },
  );

  test.each([
    ['product_id', '104'],
    ['product_id', 0],
    ['product_id', 1.5],
    ['warehouse_id', -1],
    ['current_stock', -1],
    ['current_stock', '4'],
    ['threshold', null],
    ['alert_type', '   '],
    ['alert_type', 5],
    ['message', ''],
  ])('%s inválido: %p', async (campo, valor) => {
    const res = await request(app).post(URL).send({ ...alertaValida(), [campo]: valor });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('DATOS_INVALIDOS');
    expect(res.body.mensaje).toHaveProperty(campo);
  });

  test('reporta todos los campos con error a la vez', async () => {
    const res = await request(app).post(URL).send({});
    expect(res.status).toBe(400);
    expect(Object.keys(res.body.mensaje).sort()).toEqual(
      ['alert_type', 'current_stock', 'message', 'product_id', 'threshold', 'warehouse_id'],
    );
  });

  test('cuerpo que no es objeto', async () => {
    const res = await request(app).post(URL).send([alertaValida()]);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('DATOS_INVALIDOS');
  });

  test('JSON malformado', async () => {
    const res = await request(app).post(URL).set('Content-Type', 'application/json').send('{"alert_type":');
    expect(res.status).toBe(400);
    expect(res.body).toEqual({ error: 'DATOS_INVALIDOS', mensaje: 'El cuerpo no es un JSON válido.' });
  });

  test('cuerpo que no es JSON -> 415', async () => {
    const res = await request(app).post(URL).set('Content-Type', 'text/plain').send('hola');
    expect(res.status).toBe(415);
    expect(res.body.error).toBe('TIPO_NO_SOPORTADO');
  });
});

describe('POST /alerts: solo uso interno (403)', () => {
  test.each([
    [{ 'X-Usuario-Id': '1', 'X-Rol': 'ADMIN', 'X-Bodega-Id': '1' }],
    [{ 'X-Usuario-Id': '2' }],
    [{ 'X-Rol': 'OPERADOR_BODEGA' }],
  ])('rechaza peticiones con cabeceras del Gateway %p', async (cabeceras) => {
    const res = await request(app).post(URL).set(cabeceras).send(alertaValida());
    expect(res.status).toBe(403);
    expect(res.body.error).toBe('SIN_PERMISO');
    expect(logSpy).not.toHaveBeenCalled();
  });
});

describe('Errores de ruta y método', () => {
  test.each(['get', 'put', 'patch', 'delete'])('%s /alerts -> 405', async (metodo) => {
    const res = await request(app)[metodo](URL);
    expect(res.status).toBe(405);
    expect(res.body.error).toBe('METODO_NO_PERMITIDO');
  });

  test('ruta desconocida -> 404', async () => {
    const res = await request(app).get('/api/notifications/otra');
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: 'NO_ENCONTRADO', mensaje: 'La ruta no existe en ms-notificaciones.' });
  });

  test('ruta del contrato con prefijo duplicado no existe', async () => {
    const res = await request(app).post('/api/notifications/notifications/alerts').send(alertaValida());
    expect(res.status).toBe(404);
  });
});
