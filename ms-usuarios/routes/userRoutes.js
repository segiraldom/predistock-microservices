const express = require('express');
const router = express.Router();
const userController = require('../controllers/userController');
const { validateUserCreation } = require('../middlewares/validateRequest');

// Rutas de administración de usuarios (RF07)
router.get('/users', userController.listUsers);
router.post('/users', validateUserCreation, userController.createUser);
router.put('/users/:id', userController.updateUser);

// Consulta de roles disponibles
router.get('/roles', userController.listRoles);

module.exports = router;