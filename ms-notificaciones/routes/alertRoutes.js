// ms-notificaciones/routes/alertRoutes.js
const express = require('express');
const router = express.Router();
const alertController = require('../controllers/alertController');
const { soloRedInterna } = require('../middlewares/internalOnly');
const { exigirJson, validateAlertBody } = require('../middlewares/validateAlert');
const { metodoNoPermitido } = require('../middlewares/errores');

// RF09: alerta de stock bajo enviada por ms-existencias (uso interno)
router.route('/alerts')
  .post(soloRedInterna, exigirJson, validateAlertBody, alertController.despacharAlerta)
  .all(metodoNoPermitido);

module.exports = router;
