/* ============================================= */
/* RUTAS DE GESTIÓN DE CASOS                     */
/* CRUD completo para casos de validación        */
/* ============================================= */
const express = require('express');
const pool = require('../db.cjs');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();

/* Aplicar middleware de autenticación a todas las rutas */
router.use(authMiddleware);

/* GET /api/cases - Obtener todos los casos con su checklist */
router.get('/', async (req, res) => {
  try {
    /* Consultar todos los casos ordenados: primero los default, luego por fecha */
    const casesResult = await pool.query(
      'SELECT * FROM cases ORDER BY is_default DESC, created_at ASC'
    );
    /* Para cada caso, obtener sus preguntas del checklist */
    const cases = [];
    for (const c of casesResult.rows) {
      const checklistResult = await pool.query(
        'SELECT question FROM case_checklist WHERE case_id = $1 ORDER BY sort_order ASC',
        [c.id]
      );
      /* Construir el objeto del caso con su checklist */
      cases.push({
        id: c.id,
        name: c.name,
        icon: c.icon,
        color: c.color,
        description: c.description,
        isDefault: c.is_default,
        checklist: checklistResult.rows.map(r => r.question),
      });
    }
    /* Responder con la lista de casos */
    res.json({ cases });
  } catch (err) {
    console.error('[CASES] Error al obtener casos:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* POST /api/cases - Crear un nuevo caso */
router.post('/', async (req, res) => {
  try {
    const { name, icon, color, description, checklist } = req.body;
    /* Validar campos obligatorios */
    if (!name || !checklist || checklist.length === 0) {
      return res.status(400).json({ error: 'Nombre y checklist son obligatorios' });
    }
    /* Generar un ID único para el caso */
    const id = 'CUSTOM_' + Date.now().toString(36).toUpperCase();
    /* Insertar el caso en la base de datos */
    await pool.query(
      'INSERT INTO cases (id, name, icon, color, description, is_default) VALUES ($1, $2, $3, $4, $5, FALSE)',
      [id, name, icon || '📋', color || '#3B9EFF', description || '']
    );
    /* Insertar las preguntas del checklist */
    for (let i = 0; i < checklist.length; i++) {
      if (checklist[i].trim()) {
        await pool.query(
          'INSERT INTO case_checklist (case_id, question, sort_order) VALUES ($1, $2, $3)',
          [id, checklist[i], i + 1]
        );
      }
    }
    /* Responder con el caso creado */
    res.status(201).json({
      case: { id, name, icon: icon || '📋', color: color || '#3B9EFF', description: description || '', isDefault: false, checklist: checklist.filter(q => q.trim()) },
    });
  } catch (err) {
    console.error('[CASES] Error al crear caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* PUT /api/cases/:id - Actualizar un caso existente */
router.put('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { name, icon, color, description, checklist } = req.body;
    /* Verificar que el caso existe */
    const existing = await pool.query('SELECT id FROM cases WHERE id = $1', [id]);
    if (existing.rows.length === 0) {
      return res.status(404).json({ error: 'Caso no encontrado' });
    }
    /* Actualizar los datos del caso */
    await pool.query(
      'UPDATE cases SET name = $1, icon = $2, color = $3, description = $4 WHERE id = $5',
      [name, icon, color, description, id]
    );
    /* Eliminar las preguntas anteriores y insertar las nuevas */
    await pool.query('DELETE FROM case_checklist WHERE case_id = $1', [id]);
    for (let i = 0; i < checklist.length; i++) {
      if (checklist[i].trim()) {
        await pool.query(
          'INSERT INTO case_checklist (case_id, question, sort_order) VALUES ($1, $2, $3)',
          [id, checklist[i], i + 1]
        );
      }
    }
    /* Responder con éxito */
    res.json({ message: 'Caso actualizado' });
  } catch (err) {
    console.error('[CASES] Error al actualizar caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* DELETE /api/cases/:id - Eliminar un caso */
router.delete('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    /* Verificar que el caso existe */
    const existing = await pool.query('SELECT id FROM cases WHERE id = $1', [id]);
    if (existing.rows.length === 0) {
      return res.status(404).json({ error: 'Caso no encontrado' });
    }
    /* Eliminar el caso (cascade elimina checklist automáticamente) */
    await pool.query('DELETE FROM cases WHERE id = $1', [id]);
    /* Responder con éxito */
    res.json({ message: 'Caso eliminado' });
  } catch (err) {
    console.error('[CASES] Error al eliminar caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
