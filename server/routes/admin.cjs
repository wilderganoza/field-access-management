/* ============================================= */
/* RUTAS DE ADMINISTRACIÓN DE USUARIOS           */
/* CRUD completo: crear, editar, desactivar,     */
/* eliminar usuarios (solo acceso admin)         */
/* ============================================= */
const express = require('express');
const bcrypt = require('bcryptjs');
const pool = require('../db.cjs');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();

/* Aplicar middleware de autenticación a todas las rutas */
router.use(authMiddleware);

/* Middleware para verificar que el usuario es admin */
function adminOnly(req, res, next) {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Acceso restringido a administradores' });
  }
  next();
}

/* Aplicar verificación de admin a todas las rutas */
router.use(adminOnly);

/* GET /api/admin/users - Obtener todos los usuarios */
router.get('/users', async (req, res) => {
  try {
    /* Consultar todos los usuarios con sus datos (sin contraseña) */
    const result = await pool.query(
      `SELECT id, username, role, full_name, email, department, position, is_active, created_at
       FROM users ORDER BY created_at ASC`
    );
    /* Responder con la lista de usuarios */
    res.json({ users: result.rows });
  } catch (err) {
    console.error('[ADMIN] Error al obtener usuarios:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* POST /api/admin/users - Crear un nuevo usuario */
router.post('/users', async (req, res) => {
  try {
    const { username, password, role, full_name, email, department, position } = req.body;
    /* Validar campos obligatorios */
    if (!username || !password) {
      return res.status(400).json({ error: 'Usuario y contraseña son obligatorios' });
    }
    /* Verificar que el username no exista */
    const existing = await pool.query('SELECT id FROM users WHERE username = $1', [username]);
    if (existing.rows.length > 0) {
      return res.status(409).json({ error: 'El nombre de usuario ya existe' });
    }
    /* Hashear la contraseña */
    const hashedPassword = await bcrypt.hash(password, 10);
    /* Insertar el nuevo usuario */
    const result = await pool.query(
      `INSERT INTO users (username, password, role, full_name, email, department, position, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
       RETURNING id, username, role, full_name, email, department, position, is_active, created_at`,
      [username, hashedPassword, role || 'operador', full_name || '', email || '', department || '', position || '']
    );
    /* Crear registro de settings para el usuario */
    await pool.query('INSERT INTO user_settings (user_id) VALUES ($1)', [result.rows[0].id]);
    /* Responder con el usuario creado */
    res.status(201).json({ user: result.rows[0] });
  } catch (err) {
    console.error('[ADMIN] Error al crear usuario:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* PUT /api/admin/users/:id - Actualizar un usuario */
router.put('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { username, password, role, full_name, email, department, position, is_active } = req.body;
    /* Verificar que el usuario existe */
    const existing = await pool.query('SELECT id FROM users WHERE id = $1', [id]);
    if (existing.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado' });
    }
    /* Si se cambia el username, verificar que no exista */
    if (username) {
      const duplicate = await pool.query('SELECT id FROM users WHERE username = $1 AND id != $2', [username, id]);
      if (duplicate.rows.length > 0) {
        return res.status(409).json({ error: 'El nombre de usuario ya está en uso' });
      }
    }
    /* Construir la query de actualización dinámicamente */
    const fields = [];
    const values = [];
    let paramIndex = 1;
    /* Agregar cada campo proporcionado */
    if (username !== undefined) { fields.push(`username = $${paramIndex++}`); values.push(username); }
    if (role !== undefined) { fields.push(`role = $${paramIndex++}`); values.push(role); }
    if (full_name !== undefined) { fields.push(`full_name = $${paramIndex++}`); values.push(full_name); }
    if (email !== undefined) { fields.push(`email = $${paramIndex++}`); values.push(email); }
    if (department !== undefined) { fields.push(`department = $${paramIndex++}`); values.push(department); }
    if (position !== undefined) { fields.push(`position = $${paramIndex++}`); values.push(position); }
    if (is_active !== undefined) { fields.push(`is_active = $${paramIndex++}`); values.push(is_active); }
    /* Si se proporcionó nueva contraseña, hashearla */
    if (password) {
      const hashed = await bcrypt.hash(password, 10);
      fields.push(`password = $${paramIndex++}`);
      values.push(hashed);
    }
    /* Si no hay campos para actualizar, retornar error */
    if (fields.length === 0) {
      return res.status(400).json({ error: 'No se proporcionaron campos para actualizar' });
    }
    /* Ejecutar la actualización */
    values.push(id);
    await pool.query(`UPDATE users SET ${fields.join(', ')} WHERE id = $${paramIndex}`, values);
    /* Obtener el usuario actualizado */
    const updated = await pool.query(
      'SELECT id, username, role, full_name, email, department, position, is_active, created_at FROM users WHERE id = $1',
      [id]
    );
    /* Responder con el usuario actualizado */
    res.json({ user: updated.rows[0] });
  } catch (err) {
    console.error('[ADMIN] Error al actualizar usuario:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* DELETE /api/admin/users/:id - Eliminar un usuario */
router.delete('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;
    /* No permitir que un admin se elimine a sí mismo */
    if (parseInt(id) === req.user.id) {
      return res.status(403).json({ error: 'No puedes eliminar tu propia cuenta' });
    }
    /* Verificar que el usuario existe */
    const existing = await pool.query('SELECT id FROM users WHERE id = $1', [id]);
    if (existing.rows.length === 0) {
      return res.status(404).json({ error: 'Usuario no encontrado' });
    }
    /* Eliminar el usuario (cascade elimina settings) */
    await pool.query('DELETE FROM users WHERE id = $1', [id]);
    /* Responder con éxito */
    res.json({ message: 'Usuario eliminado' });
  } catch (err) {
    console.error('[ADMIN] Error al eliminar usuario:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
