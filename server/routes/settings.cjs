/* ============================================= */
/* RUTAS DE CONFIGURACIÓN GLOBAL                */
/* Gestión de API key compartida (una sola)     */
/* ============================================= */
const express = require('express');
const pool = require('../db.cjs');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();

/* Aplicar middleware de autenticación a todas las rutas */
router.use(authMiddleware);

/* GET /api/settings/api-key - Obtener estado de la API key global */
router.get('/api-key', async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT value FROM global_settings WHERE key = 'openai_api_key'"
    );
    if (result.rows.length === 0 || !result.rows[0].value) {
      return res.json({ configured: false, hint: '' });
    }
    const apiKey = result.rows[0].value;
    res.json({ configured: true, hint: apiKey.slice(-4) });
  } catch (err) {
    console.error('[SETTINGS] Error al obtener API key:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* PUT /api/settings/api-key - Guardar o actualizar la API key global */
router.put('/api-key', async (req, res) => {
  try {
    const { apiKey } = req.body;
    if (!apiKey || !apiKey.trim()) {
      return res.status(400).json({ error: 'API Key es obligatoria' });
    }
    await pool.query(
      `INSERT INTO global_settings (key, value) VALUES ('openai_api_key', $1)
       ON CONFLICT (key) DO UPDATE SET value = $1`,
      [apiKey.trim()]
    );
    res.json({ message: 'API Key guardada correctamente', hint: apiKey.trim().slice(-4) });
  } catch (err) {
    console.error('[SETTINGS] Error al guardar API key:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* DELETE /api/settings/api-key - Eliminar la API key global */
router.delete('/api-key', async (req, res) => {
  try {
    await pool.query(
      "DELETE FROM global_settings WHERE key = 'openai_api_key'"
    );
    res.json({ message: 'API Key eliminada' });
  } catch (err) {
    console.error('[SETTINGS] Error al eliminar API key:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* GET /api/settings/api-key/full - Obtener la API key completa (para el pipeline) */
router.get('/api-key/full', async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT value FROM global_settings WHERE key = 'openai_api_key'"
    );
    if (result.rows.length === 0 || !result.rows[0].value) {
      return res.status(404).json({ error: 'API Key no configurada' });
    }
    res.json({ apiKey: result.rows[0].value });
  } catch (err) {
    console.error('[SETTINGS] Error al obtener API key completa:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
