// ms-usuarios/routes/authRoutes.js
const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const { validateLoginBody } = require('../middlewares/validateRequest');

// Rutas de autenticación según la tabla del Gateway
router.post('/login', validateLoginBody, authController.login);
router.all('/me', authController.getProfile);
router.all('/logout', authController.logout);

// Recuperación y cambio de credenciales
router.post('/recuperar-password', authController.forgotPassword);
router.post('/restablecer-password', authController.resetPassword);
router.all('/cambiar-password', authController.changePassword);

// Aliases en inglés por compatibilidad con tests previos
router.post('/forgot-password', authController.forgotPassword);
router.post('/reset-password', authController.resetPassword);
router.all('/change-password', authController.changePassword);

module.exports = router;