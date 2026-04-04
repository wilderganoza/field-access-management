/* ============================================= */
/* RUTAS DE AUTENTICACIÓN                        */
/* Login, registro y obtener perfil              */
/* ============================================= */
const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const pool = require('../db.cjs');
const { authMiddleware, JWT_SECRET } = require('../middleware.cjs');

const router = express.Router();

/* POST /api/auth/login - Iniciar sesión */
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    /* Validar que se proporcionaron los campos */
    if (!username || !password) {
      return res.status(400).json({ error: 'Usuario y contraseña son obligatorios' });
    }
    /* Buscar el usuario en la base de datos */
    const result = await pool.query('SELECT * FROM users WHERE username = $1', [username]);
    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Credenciales incorrectas' });
    }
    const user = result.rows[0];
    /* Verificar si la cuenta está activa */
    if (user.is_active === false) {
      return res.status(403).json({ error: 'Cuenta desactivada. Contacta al administrador.' });
    }
    /* Verificar la contraseña */
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(401).json({ error: 'Credenciales incorrectas' });
    }
    /* Generar token JWT */
    const token = jwt.sign({ id: user.id, username: user.username, role: user.role }, JWT_SECRET, { expiresIn: '7d' });
    /* Responder con el usuario y el token */
    res.json({ user: { id: user.id, username: user.username, role: user.role }, token });
  } catch (err) {
    console.error('[AUTH] Error en login:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* GET /api/auth/me - Obtener perfil del usuario autenticado */
router.get('/me', authMiddleware, async (req, res) => {
  try {
    /* Buscar el usuario por su ID del token */
    const result = await pool.query('SELECT id, username, role FROM users WHERE id = $1', [req.user.id]);
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado' });
    }
    /* Responder con los datos del usuario */
    res.json({ user: result.rows[0] });
  } catch (err) {
    console.error('[AUTH] Error en perfil:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
