// ms-usuarios/routes/userRoutes.js
const express = require('express');
const router = express.Router();
const userController = require('../controllers/userController');
const { validateUserCreation } = require('../middlewares/validateRequest');

// Rutas de usuarios (quedan en /api/usuarios/usuarios)
router.get('/usuarios', userController.listUsers);
router.post('/usuarios', validateUserCreation, userController.createUser);
router.put('/usuarios/:id', userController.updateUser);
router.delete('/usuarios/:id', userController.updateUser); // O baja lógica (activo: false)

// Alias /users por compatibilidad
router.get('/users', userController.listUsers);
router.post('/users', validateUserCreation, userController.createUser);
router.put('/users/:id', userController.updateUser);

// Catálogo de roles (queda en /api/usuarios/roles)
router.get('/roles', userController.listRoles);

module.exports = router;