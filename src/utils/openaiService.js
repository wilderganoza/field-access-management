/* ============================================= */
/* SERVICIO DE COMUNICACIÓN CON OPENAI API       */
/* Responses API + GPT-4.1 (1M tokens)           */
/* Formato de respuesta estrictamente controlado  */
/* ============================================= */
import * as XLSX from 'xlsx';
import { fileToBase64, cleanJsonResponse, getExtension } from './fileHelpers';

const API_BASE = 'https://api.openai.com/v1';
const MODEL = 'gpt-4.1';

/* Fecha actual formateada para incluir en los prompts (verificación de vigencias) */
function getFechaActual() {
  return new Date().toLocaleDateString('es-PE', { year: 'numeric', month: 'long', day: 'numeric' });
}

/* Reemplaza {{VARIABLE}} en una plantilla de prompt con los valores dados */
function applyTemplate(template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) =>
    vars[key] !== undefined ? vars[key] : `{{${key}}}`
  );
}

/* Convierte un nombre a Title Case: "JUAN PEREZ" → "Juan Perez" */
function toTitleCase(str) {
  if (!str) return str;
  return str
    .toLowerCase()
    .split(/\s+/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
    .trim();
}

/* ============================================= */
/* LLAMADA AL RESPONSES API                      */
/* ============================================= */
async function responsesCall(apiKey, instructions, input, maxTokens = 16384) {
  const response = await fetch(`${API_BASE}/responses`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: MODEL,
      instructions,
      input,
      temperature: 0.05,
      max_output_tokens: maxTokens,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || `Error de OpenAI: ${response.status}`);
  }
  const data = await response.json();
  const outputMsg = data.output?.find(o => o.type === 'message');
  if (outputMsg) {
    const textBlock = outputMsg.content?.find(c => c.type === 'output_text');
    return textBlock?.text || '';
  }
  return '';
}

/* ============================================= */
/* PARSEAR DOCX A TEXTO PLANO                    */
/* Usa JSZip para extraer word/document.xml      */
/* ============================================= */
async function docxToText(file) {
  try {
    const JSZip = (await import('jszip')).default;
    const arrayBuffer = await file.arrayBuffer();
    const zip = await JSZip.loadAsync(arrayBuffer);
    /* Extraer el documento principal */
    const docXmlFile = zip.file('word/document.xml');
    if (!docXmlFile) return `=== DOCUMENTO WORD: ${file.name} (no se encontró contenido) ===`;
    const xml = await docXmlFile.async('string');
    /* Convertir XML a texto legible */
    const text = xml
      .replace(/<w:p[ >]/g, '\n')
      .replace(/<w:br[^/]*/g, '\n')
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    return `=== DOCUMENTO WORD: ${file.name} ===\n${text || '(sin texto extraíble)'}`;
  } catch (err) {
    return `=== DOCUMENTO WORD: ${file.name} (error al leer: ${err.message}) ===`;
  }
}

/* ============================================= */
/* PARSEAR EXCEL A TEXTO LEGIBLE                 */
/* Convierte cada hoja a una tabla de texto      */
/* ============================================= */
async function excelToText(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        let text = `=== ARCHIVO EXCEL: ${file.name} ===\n`;
        for (const sheetName of workbook.SheetNames) {
          const sheet = workbook.Sheets[sheetName];
          const csv = XLSX.utils.sheet_to_csv(sheet, { FS: ' | ', RS: '\n' });
          /* Filtrar filas vacías */
          const rows = csv.split('\n').filter(r => r.replace(/[\s|]/g, '').length > 0);
          if (rows.length > 0) {
            text += `\n--- Hoja: ${sheetName} ---\n${rows.join('\n')}\n`;
          }
        }
        resolve(text);
      } catch (err) {
        resolve(`=== ARCHIVO EXCEL: ${file.name} (error al leer: ${err.message}) ===\n`);
      }
    };
    reader.onerror = () => resolve(`=== ARCHIVO EXCEL: ${file.name} (no se pudo leer) ===\n`);
    reader.readAsArrayBuffer(file);
  });
}

/* ============================================= */
/* CONVERTIR ARCHIVO A CONTENT BLOCK             */
/* Soporta: imágenes, PDFs, Excel, Word, texto  */
/* Cada conversión tiene try-catch propio        */
/* ============================================= */
async function fileToContentBlock(file) {
  const ext = getExtension(file.name).replace('.', '').toLowerCase();
  try {
    /* Imágenes → input_image */
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
      const base64 = await fileToBase64(file);
      const mimeType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
      return { type: 'input_image', image_url: `data:${mimeType};base64,${base64}` };
    }
    /* PDFs → input_file (Responses API) */
    if (ext === 'pdf') {
      const base64 = await fileToBase64(file);
      return { type: 'input_file', filename: file.name, file_data: `data:application/pdf;base64,${base64}` };
    }
    /* Word (.docx) → extraer texto con JSZip */
    if (ext === 'docx') {
      const text = await docxToText(file);
      return { type: 'input_text', text };
    }
    /* Excel (.xlsx, .xls, .xlsm) → convertir a texto */
    if (['xlsx', 'xls', 'xlsm'].includes(ext)) {
      const text = await excelToText(file);
      return { type: 'input_text', text };
    }
    /* CSV / TXT → texto plano */
    if (['csv', 'txt'].includes(ext)) {
      const text = await file.text();
      return { type: 'input_text', text: `=== ARCHIVO: ${file.name} ===\n${text}` };
    }
  } catch (err) {
    /* Si falla la conversión, incluir un aviso de error en lugar de silenciarlo */
    return {
      type: 'input_text',
      text: `=== ARCHIVO: ${file.name} (ERROR AL PROCESAR: ${err.message}) ===\nEl archivo existe pero no se pudo leer correctamente.`,
    };
  }
  return null;
}

/* ============================================= */
/* NORMALIZADORES DE RESPUESTA                   */
/* Garantizan formato consistente sin importar   */
/* lo que devuelva el modelo                     */
/* ============================================= */

/**
 * Normaliza la respuesta del checklist.
 * Siempre retorna: { personas: [{ nombre: string, resultados: [{ pregunta, resultado, explicacion }] }] }
 */
function normalizeChecklist(raw, expectedQuestions) {
  const parsed = JSON.parse(cleanJsonResponse(raw));

  /* Extraer el array de personas de cualquier formato posible */
  let personas = parsed.personas || parsed.persons || parsed.people || parsed.results || parsed.evaluaciones || [];

  /* Si el resultado es un array directo de {pregunta, resultado, explicacion} (formato plano) */
  if (personas.length > 0 && personas[0].pregunta && !personas[0].resultados) {
    personas = [{ nombre: 'Evaluación General', resultados: personas }];
  }

  /* Si el resultado es un array directo de {nombre, resultados} pero dentro de otra key */
  if (!Array.isArray(personas)) {
    personas = [];
  }

  /* Normalizar cada persona */
  const normalized = personas.map(p => {
    /* Aplicar Title Case al nombre para consistencia visual */
    const nombre = toTitleCase(p.nombre || p.name || p.persona || p.person || 'Sin nombre');

    /* Extraer resultados de cualquier formato */
    let resultados = p.resultados || p.results || p.checklist || p.items || [];

    /* Normalizar cada resultado */
    resultados = resultados.map(r => ({
      pregunta: r.pregunta || r.question || r.item || '',
      resultado: normalizeVerdict(r.resultado || r.result || r.status || r.estado || 'PENDIENTE'),
      explicacion: r.explicacion || r.explanation || r.detalle || r.detail || r.observacion || '',
    }));

    /* Si faltan preguntas del checklist, agregarlas como PENDIENTE */
    if (resultados.length < expectedQuestions.length) {
      const existingQuestions = new Set(resultados.map(r => r.pregunta.toLowerCase().trim()));
      for (const q of expectedQuestions) {
        if (!existingQuestions.has(q.toLowerCase().trim())) {
          resultados.push({
            pregunta: q,
            resultado: 'PENDIENTE',
            explicacion: 'No evaluado por la IA - documento no encontrado o no analizado.',
          });
        }
      }
    }

    return { nombre, resultados };
  });

  return { personas: normalized };
}

/**
 * Normaliza un veredicto individual a uno de los 3 valores válidos.
 */
function normalizeVerdict(value) {
  const v = String(value).toUpperCase().trim();
  if (v.includes('APROB') || v === 'OK' || v === 'PASS' || v === 'YES' || v === 'SÍ' || v === 'SI') return 'APROBADO';
  if (v.includes('RECHAZ') || v === 'FAIL' || v === 'NO' || v === 'REJECT') return 'RECHAZADO';
  return 'PENDIENTE';
}

/**
 * Calcula el veredicto general a partir del checklist normalizado.
 */
export function computeOverallVerdict(checklistData) {
  const personas = checklistData.personas || [];
  const allResults = personas.flatMap(p => p.resultados || []);
  const rejected = allResults.filter(r => r.resultado === 'RECHAZADO').length;
  const pending = allResults.filter(r => r.resultado === 'PENDIENTE').length;
  if (rejected > 0) return 'RECHAZADO';
  if (pending > 0) return 'PENDIENTE';
  return 'APROBADO';
}

/* ============================================= */
/* PASO 2: ANALIZAR, VALIDAR Y RESUMIR (TODO EN  */
/* UNA SOLA LLAMADA A LA IA)                     */
/* Recibe los archivos directamente, los procesa */
/* y valida el checklist + genera el resumen     */
/* ============================================= */
export async function validateAndSummarize(apiKey, files, checklist, emailData, caseName, customPrompts = {}) {
  const checklistText = checklist.map((q, i) => `${i + 1}. ${q}`).join('\n');
  const fechaActual = getFechaActual();

  /* Clasificar archivos por tipo de soporte */
  const SUPPORTED = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'docx', 'xlsx', 'xls', 'xlsm', 'csv', 'txt'];
  const supportedFiles = [];
  const unsupportedFiles = [];
  for (const file of files) {
    const ext = getExtension(file.name).replace('.', '').toLowerCase();
    if (SUPPORTED.includes(ext)) supportedFiles.push(file);
    else unsupportedFiles.push(file.name);
  }

  /* Lista numerada de TODOS los archivos — se inyecta en el prompt */
  const fileListText = supportedFiles
    .map((f, i) => `  ${i + 1}. ${f.name}`)
    .join('\n');

  const defaultInstructions = `Eres un analista QHSE senior de OIG Perú especializado en verificación de permisos de acceso.

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
}`;

  const instructions = applyTemplate(
    customPrompts.validate_and_summarize || defaultInstructions,
    {
      FECHA_ACTUAL: fechaActual,
      NUM_ARCHIVOS: supportedFiles.length,
      LISTA_ARCHIVOS: fileListText,
      NUM_PREGUNTAS: checklist.length,
      CASO: caseName,
      REMITENTE: emailData.from || 'N/A',
      ASUNTO: emailData.subject || 'Sin asunto',
    }
  );

  /* Construir los content blocks con todos los archivos */
  const content = [];

  /* Bloque inicial: lista explícita de archivos para que la IA no omita ninguno */
  content.push({
    type: 'input_text',
    text: `Debes analizar TODOS los siguientes ${supportedFiles.length} archivos. No omitas ninguno:\n${fileListText}\n\nA continuación recibirás cada archivo:`,
  });

  let processedCount = 0;
  let failedCount = 0;

  for (let i = 0; i < supportedFiles.length; i++) {
    const file = supportedFiles[i];
    content.push({ type: 'input_text', text: `\n--- ARCHIVO ${i + 1}/${supportedFiles.length}: ${file.name} ---` });
    try {
      const block = await fileToContentBlock(file);
      if (block) {
        content.push(block);
        processedCount++;
      } else {
        content.push({
          type: 'input_text',
          text: `[AVISO: El archivo "${file.name}" no pudo convertirse a un formato legible por la IA.]`,
        });
        failedCount++;
      }
    } catch (err) {
      content.push({
        type: 'input_text',
        text: `[ERROR al procesar "${file.name}": ${err.message}]`,
      });
      failedCount++;
    }
  }

  /* Bloque final: checklist + instrucción de cierre */
  content.push({
    type: 'input_text',
    text: `\n--- FIN DE ARCHIVOS ---\nHas recibido ${supportedFiles.length} archivos en total` +
      (unsupportedFiles.length > 0 ? ` (${unsupportedFiles.length} formato no soportado omitidos: ${unsupportedFiles.join(', ')})` : '') + `.\n\n` +
      `DATOS DEL CORREO:\n` +
      `- Remitente: ${emailData.from || 'N/A'}\n` +
      `- Asunto: ${emailData.subject || 'Sin asunto'}\n` +
      `- Fecha del correo: ${emailData.date || 'N/A'}\n\n` +
      `TIPO DE CASO: ${caseName}\n\n` +
      `CHECKLIST (${checklist.length} preguntas — cada persona debe tener exactamente ${checklist.length} resultados):\n${checklistText}\n\n` +
      `Ahora completa las 3 fases y responde SOLO con el JSON. Nada más.`,
  });

  const response = await responsesCall(apiKey, instructions, [{ role: 'user', content }], 32768);

  /* Normalizar el checklist desde la respuesta */
  const checklistResults = normalizeChecklist(response, checklist);

  /* Extraer el resumen del mismo JSON */
  let summaryText = '';
  try {
    const parsed = JSON.parse(cleanJsonResponse(response));
    summaryText = parsed.resumen || parsed.summary || parsed.resumen_ejecutivo || '';
  } catch {
    /* Si no se puede parsear, el resumen queda vacío — el checklist ya fue normalizado */
  }

  return { checklistResults, summaryText, processedCount, failedCount, totalFiles: supportedFiles.length };
}
