/* ============================================= */
/* RUTA DE EXTRACCIÓN DE ARCHIVOS RAR/7Z        */
/* Usa unrar-js para descomprimir en servidor    */
/* ============================================= */
const express = require('express');
const multer = require('multer');
const { unrar } = require('unrar-js');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();

/* Configurar multer para recibir archivos en memoria */
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024 }, /* 100 MB máximo */
});

/* Aplicar middleware de autenticación */
router.use(authMiddleware);

/* POST /api/extract - Extraer archivos de un RAR */
router.post('/', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No se proporcionó archivo' });
    }

    const buffer = req.file.buffer;
    const originalName = req.file.originalname || 'archivo';
    const ext = originalName.split('.').pop().toLowerCase();

    let extractedFiles = [];

    if (ext === 'rar') {
      /* Extraer archivos del RAR */
      const entries = unrar(buffer);
      for (const entry of entries) {
        /* Saltar directorios (sin contenido) */
        if (!entry.fileData || entry.fileData.length === 0) continue;
        /* Obtener nombre limpio del archivo */
        const name = entry.filename.split('/').pop().split('\\').pop();
        if (!name) continue;
        /* Convertir a base64 */
        const base64 = Buffer.from(entry.fileData).toString('base64');
        extractedFiles.push({ name, base64, size: entry.fileData.length });
      }
    } else {
      return res.status(400).json({ error: 'Formato no soportado. Solo RAR.' });
    }

    res.json({ files: extractedFiles, origin: originalName });
  } catch (err) {
    console.error('[EXTRACT] Error al extraer archivo:', err.message);
    res.status(500).json({ error: 'Error al extraer el archivo: ' + err.message });
  }
});

module.exports = router;
