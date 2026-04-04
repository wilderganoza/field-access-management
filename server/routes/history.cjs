/* ============================================= */
/* RUTAS DE HISTORIAL DE SOLICITUDES             */
/* Guardar y consultar análisis procesados       */
/* Soporta checklist por persona/vehículo        */
/* ============================================= */
const express = require('express');
const pool = require('../db.cjs');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();

/* Aplicar middleware de autenticación a todas las rutas */
router.use(authMiddleware);

/* ============================================= */
/* HELPER: Reconstruir checklistResults desde DB  */
/* Agrupa por persona si hay person_name          */
/* ============================================= */
function buildChecklistFromRows(rows) {
  /* Si no hay resultados, retornar array vacío */
  if (!rows || rows.length === 0) return [];
  /* Verificar si hay datos por persona */
  const hasPersons = rows.some(r => r.person_name && r.person_name.trim() !== '');
  if (hasPersons) {
    /* Agrupar por persona */
    const personMap = {};
    for (const r of rows) {
      const name = r.person_name || 'Sin nombre';
      if (!personMap[name]) {
        personMap[name] = { nombre: name, resultados: [] };
      }
      personMap[name].resultados.push({
        pregunta: r.question,
        resultado: r.result,
        explicacion: r.explanation,
      });
    }
    return Object.values(personMap);
  }
  /* Formato plano (compatibilidad con datos antiguos) */
  return rows.map(r => ({
    pregunta: r.question,
    resultado: r.result,
    explicacion: r.explanation,
  }));
}

/* ============================================= */
/* HELPER: Guardar checklistResults en DB         */
/* Soporta formato por persona y formato plano   */
/* ============================================= */
async function saveChecklistResults(analysisId, checklistResults) {
  if (!checklistResults || !Array.isArray(checklistResults)) {
    console.log('[CHECKLIST] checklistResults vacío o no es array:', typeof checklistResults);
    return;
  }
  console.log(`[CHECKLIST] Guardando checklist para análisis ${analysisId}, ${checklistResults.length} entradas`);
  /* Detectar si viene en formato por persona [{nombre, resultados}] */
  if (checklistResults.length > 0 && checklistResults[0].nombre && checklistResults[0].resultados) {
    /* Formato por persona */
    console.log(`[CHECKLIST] Formato por persona: ${checklistResults.length} personas`);
    for (const persona of checklistResults) {
      console.log(`[CHECKLIST]   Persona: ${persona.nombre}, ${persona.resultados.length} resultados`);
      for (const result of persona.resultados) {
        await pool.query(
          'INSERT INTO analysis_checklist_results (analysis_id, person_name, question, result, explanation) VALUES ($1, $2, $3, $4, $5)',
          [analysisId, persona.nombre, result.pregunta, result.resultado, result.explicacion || '']
        );
      }
    }
    console.log('[CHECKLIST] Guardado por persona completado.');
  } else {
    /* Formato plano [{pregunta, resultado, explicacion}] */
    console.log(`[CHECKLIST] Formato plano: ${checklistResults.length} items`);
    for (const result of checklistResults) {
      if (result.pregunta) {
        await pool.query(
          'INSERT INTO analysis_checklist_results (analysis_id, person_name, question, result, explanation) VALUES ($1, $2, $3, $4, $5)',
          [analysisId, '', result.pregunta, result.resultado, result.explicacion || '']
        );
      }
    }
    console.log('[CHECKLIST] Guardado plano completado.');
  }
}

/* GET /api/history - Obtener todo el historial del usuario */
router.get('/', async (req, res) => {
  try {
    /* Consultar todo el historial ordenado por fecha descendente */
    const historyResult = await pool.query(
      'SELECT * FROM analysis_history ORDER BY created_at DESC'
    );
    /* Para cada entrada, obtener archivos y resultados del checklist */
    const history = [];
    for (const entry of historyResult.rows) {
      /* Obtener archivos de la solicitud */
      const filesResult = await pool.query(
        'SELECT name, file_type, status FROM analysis_files WHERE analysis_id = $1',
        [entry.id]
      );
      /* Obtener resultados del checklist */
      const checklistResult = await pool.query(
        'SELECT person_name, question, result, explanation FROM analysis_checklist_results WHERE analysis_id = $1 ORDER BY id ASC',
        [entry.id]
      );
      /* Construir el objeto completo de la entrada */
      history.push({
        id: entry.id,
        requestName: entry.request_name || '',
        timestamp: entry.created_at,
        emailData: {
          from: entry.email_from,
          to: entry.email_to,
          subject: entry.email_subject,
          date: entry.email_date,
          body: entry.email_body,
        },
        caseId: entry.case_id,
        caseName: entry.case_name,
        caseIcon: entry.case_icon,
        caseColor: entry.case_color,
        files: filesResult.rows.map(f => ({ name: f.name, type: f.file_type, status: f.status })),
        checklistResults: buildChecklistFromRows(checklistResult.rows),
        summary: entry.summary,
        verdict: entry.verdict,
      });
    }
    /* Responder con el historial completo */
    res.json({ history });
  } catch (err) {
    console.error('[HISTORY] Error al obtener historial:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* POST /api/history - Guardar un nuevo análisis en el historial */
router.post('/', async (req, res) => {
  try {
    const { id, requestName, emailData, caseId, caseName, caseIcon, caseColor, files, checklistResults, summary, verdict } = req.body;
    console.log(`[HISTORY] POST recibido: id=${id}, caso=${caseName}, archivos=${files?.length}, checklist=${checklistResults?.length} personas`);
    /* Insertar la entrada principal del historial */
    await pool.query(
      `INSERT INTO analysis_history (id, user_id, request_name, case_id, case_name, case_icon, case_color,
        email_from, email_to, email_subject, email_date, email_body, summary, verdict)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)`,
      [id, req.user.id, requestName || '', caseId, caseName, caseIcon, caseColor,
        emailData.from, emailData.to, emailData.subject, emailData.date, emailData.body,
        summary, verdict]
    );
    /* Insertar los archivos procesados */
    for (const file of files) {
      await pool.query(
        'INSERT INTO analysis_files (analysis_id, name, file_type, status) VALUES ($1, $2, $3, $4)',
        [id, file.name, file.type, file.status]
      );
    }
    /* Insertar los resultados del checklist (soporta ambos formatos) */
    await saveChecklistResults(id, checklistResults);
    /* Responder con éxito */
    res.status(201).json({ message: 'Análisis guardado en el historial' });
  } catch (err) {
    console.error('[HISTORY] Error al guardar análisis:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* GET /api/history/:id - Obtener un análisis específico */
router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    /* Consultar la entrada del historial */
    const entryResult = await pool.query(
      'SELECT * FROM analysis_history WHERE id = $1',
      [id]
    );
    if (entryResult.rows.length === 0) {
      return res.status(404).json({ error: 'Análisis no encontrado' });
    }
    const entry = entryResult.rows[0];
    /* Obtener archivos */
    const filesResult = await pool.query(
      'SELECT name, file_type, status FROM analysis_files WHERE analysis_id = $1',
      [id]
    );
    /* Obtener resultados del checklist */
    const checklistResult = await pool.query(
      'SELECT person_name, question, result, explanation FROM analysis_checklist_results WHERE analysis_id = $1 ORDER BY id ASC',
      [id]
    );
    /* Responder con la entrada completa */
    res.json({
      id: entry.id,
      requestName: entry.request_name || '',
      timestamp: entry.created_at,
      emailData: {
        from: entry.email_from,
        to: entry.email_to,
        subject: entry.email_subject,
        date: entry.email_date,
        body: entry.email_body,
      },
      caseId: entry.case_id,
      caseName: entry.case_name,
      caseIcon: entry.case_icon,
      caseColor: entry.case_color,
      files: filesResult.rows.map(f => ({ name: f.name, type: f.file_type, status: f.status })),
      checklistResults: buildChecklistFromRows(checklistResult.rows),
      summary: entry.summary,
      verdict: entry.verdict,
    });
  } catch (err) {
    console.error('[HISTORY] Error al obtener análisis:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* DELETE /api/history/:id - Eliminar un análisis del historial */
router.delete('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    /* Verificar que el análisis existe */
    const existing = await pool.query(
      'SELECT id FROM analysis_history WHERE id = $1',
      [id]
    );
    if (existing.rows.length === 0) {
      return res.status(404).json({ error: 'Análisis no encontrado' });
    }
    /* Eliminar el análisis (cascade elimina archivos y checklist) */
    await pool.query('DELETE FROM analysis_history WHERE id = $1', [id]);
    /* Responder con éxito */
    res.json({ message: 'Análisis eliminado' });
  } catch (err) {
    console.error('[HISTORY] Error al eliminar análisis:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
