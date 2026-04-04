/* ============================================= */
/* PÁGINA DEL PIPELINE DE ANÁLISIS               */
/* 3 pasos secuenciales con progreso visual      */
/* y log en tiempo real                          */
/* ============================================= */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { parseEmlFile, getExtension } from '../utils/fileHelpers';
import { validateAndSummarize, computeOverallVerdict } from '../utils/openaiService';

/* Definición de los 2 pasos del pipeline */
const STEPS = [
  { id: 1, name: 'Preparar archivos', desc: 'Parseo de correo y preparación de documentos' },
  { id: 2, name: 'Analizar, validar y resumir', desc: 'La IA lee todos los archivos, valida el checklist y genera el informe' },
];

export default function AnalysisPage({ files, requestName = '', selectedCaseId = '', onComplete }) {
  /* Estado de cada paso: 'pending' | 'active' | 'completed' | 'error' */
  const [stepStates, setStepStates] = useState(STEPS.map(() => 'pending'));
  /* Log en tiempo real */
  const [logs, setLogs] = useState([]);
  /* Indicador de si el pipeline está corriendo */
  const [running, setRunning] = useState(false);
  /* Referencia al contenedor del log para auto-scroll */
  const logRef = useRef(null);
  /* Indicador de si el pipeline ya se ejecutó */
  const hasRun = useRef(false);
  /* Obtener datos del contexto */
  const { getFullApiKey, cases, addToHistory, showToast, getPromptsForCase } = useApp();

  /* Agregar una línea al log con timestamp */
  const addLog = useCallback((text, type = '') => {
    /* Generar timestamp en formato HH:MM:SS */
    const time = new Date().toLocaleTimeString('es-PE', { hour12: false });
    setLogs(prev => [...prev, { time, text, type }]);
  }, []);

  /* Actualizar el estado de un paso específico */
  const updateStep = useCallback((index, state) => {
    setStepStates(prev => {
      const updated = [...prev];
      updated[index] = state;
      return updated;
    });
  }, []);

  /* Auto-scroll del log al agregar nuevas líneas */
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  /* Ejecutar el pipeline de análisis completo */
  const runPipeline = useCallback(async () => {
    setRunning(true);
    addLog('Iniciando pipeline de análisis...');

    /* Obtener la API key completa del backend */
    addLog('Obteniendo API key del servidor...');
    const apiKey = await getFullApiKey();
    if (!apiKey) {
      addLog('Error: No se pudo obtener la API key. Configúrala en Ajustes.', 'error');
      showToast('API Key no configurada', 'error');
      setRunning(false);
      return;
    }
    addLog('API key obtenida correctamente', 'success');

    /* Cargar los prompts del caso seleccionado */
    addLog('Cargando configuración de prompts del caso...');
    const casePrompts = await getPromptsForCase(selectedCaseId);
    addLog('Prompts cargados', 'success');

    /* Buscar el caso seleccionado por el usuario */
    const classifiedCase = cases.find(c => c.id === selectedCaseId);
    if (!classifiedCase) {
      addLog('Error: No se encontró el caso seleccionado.', 'error');
      showToast('Caso no encontrado', 'error');
      setRunning(false);
      return;
    }
    addLog(`Caso seleccionado: ${classifiedCase.icon} ${classifiedCase.name}`, 'success');
    if (requestName) addLog(`Solicitud: ${requestName}`);

    /* Variables que se van llenando a lo largo del pipeline */
    let emailData = { from: 'N/A', to: 'N/A', subject: 'Sin correo .eml', date: 'N/A', body: '', attachments: [] };
    let checklistResults = null;
    let summaryText = '';
    /* Extraer solo los archivos File del array de objetos */
    let allFiles = files.map(f => f.file);

    try {
      /* =========================================== */
      /* PASO 1: PREPARAR ARCHIVOS                    */
      /* =========================================== */
      updateStep(0, 'active');
      addLog('Paso 1: Preparando archivos...');
      /* Buscar archivos .eml en la lista */
      const emlFile = allFiles.find(f => getExtension(f.name) === '.eml');
      if (emlFile) {
        addLog(`Archivo .eml encontrado: ${emlFile.name}`);
        emailData = await parseEmlFile(emlFile);
        addLog(`De: ${emailData.from}`);
        addLog(`Asunto: ${emailData.subject}`);
        addLog(`Fecha: ${emailData.date}`);
        addLog(`Adjuntos en el correo: ${emailData.attachments.length}`);
        if (emailData.attachments.length > 0) {
          allFiles = [...allFiles, ...emailData.attachments];
          addLog(`Se agregaron ${emailData.attachments.length} adjuntos del correo`, 'success');
        }
      } else {
        addLog('No se encontró archivo .eml, se usarán los archivos directos', 'warning');
      }
      const docsToProcess = allFiles.filter(f => getExtension(f.name) !== '.eml');
      /* Contar tipos de archivo para el log */
      const pdfCount  = docsToProcess.filter(f => /\.pdf$/i.test(f.name)).length;
      const imgCount  = docsToProcess.filter(f => /\.(jpg|jpeg|png|gif|webp)$/i.test(f.name)).length;
      const xlsxCount = docsToProcess.filter(f => /\.(xlsx|xls|xlsm|csv)$/i.test(f.name)).length;
      const docxCount = docsToProcess.filter(f => /\.docx$/i.test(f.name)).length;
      const txtCount  = docsToProcess.filter(f => /\.txt$/i.test(f.name)).length;
      addLog(`Total de documentos a procesar: ${docsToProcess.length}`, 'success');
      if (pdfCount  > 0) addLog(`  📄 ${pdfCount} PDFs`);
      if (imgCount  > 0) addLog(`  🖼️  ${imgCount} imágenes)`);
      if (xlsxCount > 0) addLog(`  📊 ${xlsxCount} Excel`);
      if (docxCount > 0) addLog(`  📝 ${docxCount} Word`);
      if (txtCount  > 0) addLog(`  📃 ${txtCount} texto plano`);
      updateStep(0, 'completed');

      /* =========================================== */
      /* PASO 2: ANALIZAR, VALIDAR Y RESUMIR (IA)    */
      /* =========================================== */
      updateStep(1, 'active');
      addLog('Paso 2: Enviando archivos a la IA para análisis, validación y resumen...');
      addLog(`Checklist: ${classifiedCase.checklist.length} preguntas a validar`);
      const combined = await validateAndSummarize(apiKey, docsToProcess, classifiedCase.checklist, emailData, classifiedCase.name, casePrompts);
      checklistResults = combined.checklistResults;
      summaryText = combined.summaryText;
      addLog(`✅ ${combined.processedCount}/${combined.totalFiles} archivos procesados por la IA` +
        (combined.failedCount > 0 ? ` · ⚠️ ${combined.failedCount} con error de lectura` : ''), 'success');
      const personas = checklistResults.personas;
      addLog(`${personas.length} persona(s)/vehículo(s) evaluados`, 'success');
      for (const p of personas) {
        const pa = (p.resultados || []).filter(r => r.resultado === 'APROBADO').length;
        const pr = (p.resultados || []).filter(r => r.resultado === 'RECHAZADO').length;
        const pp = (p.resultados || []).filter(r => r.resultado === 'PENDIENTE').length;
        addLog(`  ${p.nombre}: ${pa} aprobados, ${pr} rechazados, ${pp} pendientes`);
      }
      const allResults = personas.flatMap(p => p.resultados || []);
      const approved = allResults.filter(r => r.resultado === 'APROBADO').length;
      const rejected = allResults.filter(r => r.resultado === 'RECHAZADO').length;
      const pending = allResults.filter(r => r.resultado === 'PENDIENTE').length;
      addLog(`Total: ${approved} aprobados, ${rejected} rechazados, ${pending} pendientes`, 'success');
      addLog('Resumen ejecutivo generado', 'success');
      updateStep(1, 'completed');

      /* =========================================== */
      /* COMPLETAR PIPELINE Y GUARDAR RESULTADOS     */
      /* =========================================== */
      addLog('Pipeline completado exitosamente.', 'success');

      const verdict = computeOverallVerdict(checklistResults);

      const result = {
        id: Date.now().toString(36) + Math.random().toString(36).substring(2, 6),
        requestName,
        timestamp: new Date().toISOString(),
        emailData,
        caseId: classifiedCase.id,
        caseName: classifiedCase.name,
        caseIcon: classifiedCase.icon,
        caseColor: classifiedCase.color,
        files: docsToProcess.map((f) => ({
          name: f.name,
          type: getExtension(f.name),
          status: 'leído',
        })),
        checklistResults: checklistResults.personas,
        summary: summaryText,
        verdict,
      };

      /* Guardar en historial y esperar confirmación */
      addLog('Guardando resultados en el historial...');
      try {
        await addToHistory(result);
        addLog('Resultados guardados correctamente.', 'success');
      } catch (saveError) {
        addLog(`Advertencia: No se pudo guardar en el historial: ${saveError.message}`, 'error');
        showToast('Análisis completado pero no se pudo guardar en historial', 'warning');
      }

      showToast('Análisis completado', 'success');
      setTimeout(() => onComplete(result), 1500);

    } catch (error) {
      addLog(`Error en el pipeline: ${error.message}`, 'error');
      /* Marcar el paso activo como error */
      const activeIdx = stepStates.findIndex(s => s === 'active');
      updateStep(activeIdx >= 0 ? activeIdx : 0, 'error');
      showToast('Error durante el análisis: ' + error.message, 'error');
    }
    setRunning(false);
  }, [files, requestName, selectedCaseId, getFullApiKey, cases, addLog, updateStep, addToHistory, showToast, onComplete, stepStates, getPromptsForCase]);

  /* Ejecutar el pipeline al montar el componente (una sola vez) */
  useEffect(() => {
    if (!hasRun.current) {
      hasRun.current = true;
      runPipeline();
    }
  }, [runPipeline]);

  return (
    <div>
      {/* Encabezado de la página */}
      <div className="page-header">
        <h2>Análisis en Progreso</h2>
        <p>Procesando la solicitud con inteligencia artificial</p>
      </div>

      {/* Lista visual de pasos del pipeline */}
      <div className="pipeline">
        {STEPS.map((step, index) => (
          <div
            key={step.id}
            className={`pipeline-step ${stepStates[index]}`}
          >
            {/* Ícono del paso con estado visual */}
            <div className="pipeline-step-icon">
              {/* Mostrar spinner si el paso está activo */}
              {stepStates[index] === 'active' ? (
                <div className="spinner spinner-sm" />
              ) : stepStates[index] === 'completed' ? (
                '✓'
              ) : stepStates[index] === 'error' ? (
                '✕'
              ) : (
                step.id
              )}
            </div>
            {/* Nombre y descripción del paso */}
            <div>
              <div className="pipeline-step-name">{step.name}</div>
              <div className="pipeline-step-desc">{step.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Log en tiempo real del proceso */}
      <div className="pipeline-log" ref={logRef}>
        {logs.map((log, index) => (
          <div key={index} className="log-line">
            {/* Timestamp del log */}
            <span className="log-time">{log.time}</span>
            {/* Texto del log con clase de estilo según tipo */}
            <span className={`log-text ${log.type}`}>{log.text}</span>
          </div>
        ))}
        {/* Indicador de cursor parpadeante cuando está procesando */}
        {running && (
          <div className="log-line">
            <span className="log-time" />
            <span className="log-text" style={{ animation: 'blink 1s infinite' }}>▋</span>
          </div>
        )}
      </div>

      {/* Estilos para la animación del cursor */}
      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
