const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const { validateLoginBody } = require('../middlewares/validateRequest');

router.post('/login', validateLoginBody, authController.login);
router.get('/me', authController.getProfile);
router.post('/forgot-password', authController.forgotPassword);
router.post('/reset-password', authController.resetPassword);
router.post('/change-password', authController.changePassword);

module.exports = router;