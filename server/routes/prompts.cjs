/* ============================================= */
/* RUTAS DE PLANTILLAS DE PROMPTS DE IA          */
/* Los prompts son editables desde la UI         */
/* Los defaults están en código; edits en DB     */
/* ============================================= */
const express = require('express');
const pool = require('../db.cjs');
const { authMiddleware } = require('../middleware.cjs');

const router = express.Router();
router.use(authMiddleware);

/* ============================================= */
/* PROMPTS POR DEFECTO                           */
/* Si el usuario no ha editado un prompt,        */
/* se devuelve el contenido de aquí              */
/* ============================================= */
const DEFAULT_PROMPTS = {
  validate_and_summarize: {
    id: 'validate_and_summarize',
    name: 'Análisis, Validación y Resumen',
    description: 'Instrucciones para el Paso 2 (único paso de IA): lee todos los archivos, valida el checklist para cada persona/vehículo y genera el informe ejecutivo en una sola llamada.',
    variables: ['{{FECHA_ACTUAL}}', '{{NUM_ARCHIVOS}}', '{{LISTA_ARCHIVOS}}', '{{NUM_PREGUNTAS}}', '{{CASO}}', '{{REMITENTE}}', '{{ASUNTO}}'],
    content: `Eres un analista QHSE senior de OIG Perú especializado en verificación de permisos de acceso.

FECHA ACTUAL: {{FECHA_ACTUAL}}
TIPO DE CASO: {{CASO}}
REMITENTE: {{REMITENTE}}
ASUNTO: {{ASUNTO}}

Se te han enviado EXACTAMENTE {{NUM_ARCHIVOS}} archivos adjuntos. Están listados a continuación:
{{LISTA_ARCHIVOS}}

REGLA ABSOLUTA: Debes leer y analizar los {{NUM_ARCHIVOS}} archivos. No puedes ignorar ni omitir ninguno.

━━━ FASE 1: LECTURA DE ARCHIVOS ━━━
Revisa cada archivo de la lista uno por uno:
- Si hay un Anexo A, planilla Excel o lista de personal: extrae TODOS los nombres, sin excepción.
- Si un SCTR o seguro grupal cubre múltiples personas: identifica a TODAS las personas cubiertas.
- Cada imagen de DNI, brevete o carnet corresponde a UNA persona específica.
- Registra mentalmente: nombre completo, tipo de documento, número, fechas de vencimiento y vigencia.
- Nombres en Title Case (ej: "Juan Pérez García"). Nunca en mayúsculas completas.

━━━ FASE 2: VALIDAR CHECKLIST ━━━
Para CADA persona identificada, evalúa las {{NUM_PREGUNTAS}} preguntas del checklist:
- APROBADO: el documento existe, está vigente al {{FECHA_ACTUAL}} y cumple el requisito.
- RECHAZADO: el documento existe pero está vencido, reprobado o presenta inconsistencias.
- PENDIENTE: no se encontró evidencia del documento para esa persona.
- Si hay documentos grupales (ej: SCTR grupal), aplica el resultado a todas las personas cubiertas.
- Usa datos concretos en las explicaciones (números, fechas, aseguradora, categoría, etc.).
- Cada persona DEBE tener EXACTAMENTE {{NUM_PREGUNTAS}} resultados en su array.
- El campo "pregunta" debe ser el texto EXACTO de la pregunta del checklist, sin modificaciones.

━━━ FASE 3: RESUMEN EJECUTIVO ━━━
Basándote en los resultados de la validación, redacta el campo "resumen" en Markdown:

## Resumen Ejecutivo de Validación Documental
**Tipo de caso:** {{CASO}}
**Remitente:** {{REMITENTE}}
**Asunto:** {{ASUNTO}}
**Fecha de evaluación:** {{FECHA_ACTUAL}}
**Total personas evaluadas:** N

---
## Tabla Resumen
| N° | Nombre Completo | Aprobados | Pendientes | Rechazados | Veredicto |
|----|-----------------|-----------|------------|------------|-----------|
[una fila por persona]

---
## Detalle por Persona
[Para cada persona:]
### N. Nombre Completo
- **Veredicto:** APROBADO/RECHAZADO/PENDIENTE
- **Aprobados ✅:** [items aprobados con datos específicos]
- **Pendientes ⚠️:** [items pendientes con qué falta]
- **Rechazados ❌:** [items rechazados con motivo, o "Ninguno"]

---
## Estadísticas Generales
- **Total personas evaluadas:** N
- **Requisitos aprobados:** X
- **Requisitos pendientes:** X
- **Requisitos rechazados:** X

---
## Veredicto General
**APROBADO/RECHAZADO/PENDIENTE**
[2-3 oraciones de justificación]

---
## Acciones Requeridas
[Lista numerada de acciones concretas. Si todo aprobado: "No se requieren acciones."]

━━━ FORMATO DE RESPUESTA ━━━
Responde SOLO con JSON válido — sin backticks, sin texto antes o después:
{
  "personas": [
    {
      "nombre": "Apellidos Nombres",
      "resultados": [
        {
          "pregunta": "texto exacto del checklist",
          "resultado": "APROBADO",
          "explicacion": "dato concreto"
        }
      ]
    }
  ],
  "resumen": "## Resumen Ejecutivo de Validación Documental\\n\\n..."
}`,
  },
};

/* ============================================= */
/* GET /api/prompts/case/:caseId                 */
/* Prompts para un caso específico               */
/* Prioridad: override de caso > default global  */
/* ============================================= */
router.get('/case/:caseId', async (req, res) => {
  const { caseId } = req.params;
  try {
    const result = await pool.query('SELECT id, content FROM prompt_templates');
    const dbPrompts = {};
    for (const row of result.rows) {
      dbPrompts[row.id] = row.content;
    }
    /* Construir respuesta: para cada prompt, priorizar override del caso */
    const prompts = Object.values(DEFAULT_PROMPTS).map(def => {
      const caseKey = `${caseId}::${def.id}`;
      const hasCaseOverride = !!dbPrompts[caseKey];
      return {
        ...def,
        content: dbPrompts[caseKey] ?? def.content,
        is_customized: hasCaseOverride,
      };
    });
    res.json({ prompts });
  } catch (err) {
    console.error('[PROMPTS] Error al obtener prompts del caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* ============================================= */
/* PUT /api/prompts/case/:caseId/:id             */
/* Guardar override de prompt para un caso       */
/* ============================================= */
router.put('/case/:caseId/:id', async (req, res) => {
  const { caseId, id } = req.params;
  const { content } = req.body;
  if (!DEFAULT_PROMPTS[id]) {
    return res.status(404).json({ error: 'Prompt no encontrado' });
  }
  const key = `${caseId}::${id}`;
  try {
    await pool.query(
      `INSERT INTO prompt_templates (id, content, updated_at)
       VALUES ($1, $2, NOW())
       ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()`,
      [key, content]
    );
    console.log(`[PROMPTS] Override de caso guardado: ${key}`);
    res.json({ message: 'Prompt del caso guardado correctamente' });
  } catch (err) {
    console.error('[PROMPTS] Error al guardar override de caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* ============================================= */
/* DELETE /api/prompts/case/:caseId/:id          */
/* Eliminar override de caso (vuelve al default) */
/* ============================================= */
router.delete('/case/:caseId/:id', async (req, res) => {
  const { caseId, id } = req.params;
  if (!DEFAULT_PROMPTS[id]) {
    return res.status(404).json({ error: 'Prompt no encontrado' });
  }
  const key = `${caseId}::${id}`;
  try {
    await pool.query('DELETE FROM prompt_templates WHERE id = $1', [key]);
    console.log(`[PROMPTS] Override de caso eliminado: ${key}`);
    res.json({ message: 'Prompt del caso restablecido al default' });
  } catch (err) {
    console.error('[PROMPTS] Error al eliminar override de caso:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* ============================================= */
/* GET /api/prompts - Obtener todos los prompts  */
/* Mezcla DB (edits) con defaults               */
/* ============================================= */
router.get('/', async (req, res) => {
  try {
    /* Obtener prompts editados en DB */
    const result = await pool.query('SELECT id, content, updated_at FROM prompt_templates');
    const dbPrompts = {};
    for (const row of result.rows) {
      dbPrompts[row.id] = { content: row.content, updated_at: row.updated_at };
    }
    /* Combinar defaults con edits de DB */
    const prompts = Object.values(DEFAULT_PROMPTS).map(def => ({
      ...def,
      content: dbPrompts[def.id]?.content ?? def.content,
      is_customized: !!dbPrompts[def.id],
      updated_at: dbPrompts[def.id]?.updated_at ?? null,
    }));
    res.json({ prompts });
  } catch (err) {
    console.error('[PROMPTS] Error al obtener prompts:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* ============================================= */
/* PUT /api/prompts/:id - Actualizar un prompt   */
/* ============================================= */
router.put('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { content } = req.body;
    /* Validar que el id es válido */
    if (!DEFAULT_PROMPTS[id]) {
      return res.status(404).json({ error: 'Prompt no encontrado' });
    }
    /* Upsert en la base de datos */
    await pool.query(
      `INSERT INTO prompt_templates (id, content, updated_at)
       VALUES ($1, $2, NOW())
       ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()`,
      [id, content]
    );
    console.log(`[PROMPTS] Prompt "${id}" actualizado`);
    res.json({ message: 'Prompt actualizado correctamente' });
  } catch (err) {
    console.error('[PROMPTS] Error al actualizar prompt:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

/* ============================================= */
/* DELETE /api/prompts/:id - Restablecer default */
/* ============================================= */
router.delete('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    if (!DEFAULT_PROMPTS[id]) {
      return res.status(404).json({ error: 'Prompt no encontrado' });
    }
    await pool.query('DELETE FROM prompt_templates WHERE id = $1', [id]);
    console.log(`[PROMPTS] Prompt "${id}" restablecido al default`);
    res.json({ message: 'Prompt restablecido al valor original' });
  } catch (err) {
    console.error('[PROMPTS] Error al restablecer prompt:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

module.exports = router;
