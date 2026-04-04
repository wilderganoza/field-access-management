/* ============================================= */
/* PÁGINA DE NUEVA SOLICITUD                     */
/* Zona de drag & drop para cargar archivos      */
/* y botón para iniciar el análisis con IA       */
/* ============================================= */
import { useState, useRef, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { getFileIcon, formatFileSize, getExtension, isCompressed, isTempFile, decompressFile, ACCEPTED_EXTENSIONS } from '../utils/fileHelpers';

export default function NewRequestPage({ onStartAnalysis }) {
  /* Estado del nombre de la solicitud */
  const [requestName, setRequestName] = useState('');
  /* Estado del caso seleccionado */
  const [selectedCaseId, setSelectedCaseId] = useState('');
  /* Estado de los archivos cargados */
  const [files, setFiles] = useState([]);
  /* Estado del drag & drop activo */
  const [isDragging, setIsDragging] = useState(false);
  /* Estado de procesamiento (descomprimiendo archivos) */
  const [processing, setProcessing] = useState(false);
  /* Referencia al input de carpetas oculto */
  const folderInputRef = useRef(null);
  /* Obtener funciones del contexto */
  const { apiKeyConfigured, cases, showToast } = useApp();

  /* Procesar archivos cargados (validar y descomprimir) */
  const processFiles = useCallback(async (newFiles) => {
    /* Activar indicador de procesamiento */
    setProcessing(true);
    /* Array para almacenar los archivos procesados */
    const processed = [];
    for (const file of newFiles) {
      /* Saltar archivos temporales (~$ o punto inicial) */
      if (isTempFile(file.name)) continue;
      /* Obtener la extensión del archivo */
      const ext = getExtension(file.name);
      /* Verificar si la extensión es aceptada */
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        showToast(`Archivo no soportado: ${file.name}`, 'warning');
        continue;
      }
      /* Si el archivo es comprimido, intentar descomprimirlo */
      if (isCompressed(file.name)) {
        showToast(`Descomprimiendo: ${file.name}`, 'info');
        const extracted = await decompressFile(file);
        if (extracted.length > 0) {
          /* Agregar archivos extraídos con su origen */
          extracted.forEach(({ file: ef, origin }) => {
            processed.push({ file: ef, origin });
          });
          showToast(`${extracted.length} archivos extraídos de ${file.name}`, 'success');
        } else {
          /* Si la descompresión falla, tratar como archivo normal */
          processed.push({ file, origin: 'Directo' });
          showToast(`No se pudo descomprimir ${file.name}, se tratará como archivo`, 'warning');
        }
      } else {
        /* Archivo no comprimido: agregar directamente */
        processed.push({ file, origin: 'Directo' });
      }
    }
    /* Actualizar el estado con los nuevos archivos */
    if (processed.length > 0) {
      setFiles(prev => [...prev, ...processed]);
      showToast(`${processed.length} archivo(s) agregado(s)`, 'success');
    }
    /* Desactivar indicador de procesamiento */
    setProcessing(false);
  }, [showToast]);

  /* Manejar evento de drag enter */
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  /* Manejar evento de drag leave */
  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  /* Manejar evento de drag over (necesario para drop) */
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  /* Recorrer recursivamente un DirectoryEntry para obtener todos los archivos */
  const traverseEntry = (entry) => {
    return new Promise((resolve) => {
      if (entry.isFile) {
        entry.file((file) => resolve([file]), () => resolve([]));
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const allEntries = [];
        const readBatch = () => {
          reader.readEntries((entries) => {
            if (entries.length === 0) {
              Promise.all(allEntries.map(traverseEntry)).then((results) => {
                resolve(results.flat());
              });
            } else {
              allEntries.push(...entries);
              readBatch();
            }
          }, () => resolve([]));
        };
        readBatch();
      } else {
        resolve([]);
      }
    });
  };

  /* Manejar evento de drop — soporta archivos y carpetas */
  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    /* Intentar usar webkitGetAsEntry para soportar carpetas */
    const items = e.dataTransfer.items;
    if (items && items.length > 0) {
      const entries = [];
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.() || items[i].getAsEntry?.();
        if (entry) entries.push(entry);
      }
      if (entries.length > 0) {
        setProcessing(true);
        const allFiles = [];
        for (const entry of entries) {
          const files = await traverseEntry(entry);
          allFiles.push(...files);
        }
        if (allFiles.length > 0) {
          processFiles(allFiles);
          return;
        }
      }
    }
    /* Fallback: obtener archivos directamente del evento */
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      processFiles(droppedFiles);
    }
  };

  /* Manejar selección de archivos desde el input */
  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    if (selectedFiles.length > 0) {
      processFiles(selectedFiles);
    }
    /* Resetear el input para permitir seleccionar el mismo archivo */
    e.target.value = '';
  };

  /* Eliminar un archivo de la lista */
  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    showToast('Archivo eliminado', 'info');
  };

  /* Iniciar el análisis con IA */
  const handleAnalyze = () => {
    /* Verificar que haya archivos cargados */
    if (files.length === 0) {
      showToast('Carga al menos un archivo para analizar', 'warning');
      return;
    }
    /* Verificar que se haya seleccionado un caso */
    if (!selectedCaseId) {
      showToast('Selecciona un tipo de caso antes de analizar', 'warning');
      return;
    }
    /* Verificar que la API key esté configurada */
    if (!apiKeyConfigured) {
      showToast('Configura tu API Key antes de analizar', 'error');
      return;
    }
    /* Iniciar el pipeline de análisis con nombre y caso */
    onStartAnalysis(files, requestName.trim(), selectedCaseId);
  };

  return (
    <div>
      {/* Encabezado de la página */}
      <div className="page-header">
        <h2>Nueva Solicitud</h2>
        <p>Carga los archivos de la solicitud para iniciar la validación documental</p>
      </div>

      {/* Campos de configuración de la solicitud */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-body" style={{ padding: '16px 20px' }}>
          {/* Nombre de la solicitud */}
          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label className="form-label" style={{ marginBottom: '8px', display: 'block' }}>
              Nombre de la solicitud
            </label>
            <input
              type="text"
              className="form-input"
              placeholder="Ej: Habilitación Empresa Sol del Norte - Marzo 2026"
              value={requestName}
              onChange={(e) => setRequestName(e.target.value)}
            />
          </div>
          {/* Tipo de caso */}
          <div className="form-group">
            <label className="form-label" style={{ marginBottom: '8px', display: 'block' }}>
              Tipo de caso <span style={{ color: 'var(--color-error)' }}>*</span>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>
              {cases.map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedCaseId(c.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '8px',
                    border: selectedCaseId === c.id
                      ? `2px solid ${c.color}`
                      : '2px solid var(--color-border)',
                    background: selectedCaseId === c.id
                      ? c.color + '10'
                      : 'var(--color-surface)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span style={{ fontSize: '22px' }}>{c.icon}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text)' }}>
                      {c.name}
                    </div>
                    {c.description && (
                      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                        {c.description.length > 50 ? c.description.substring(0, 50) + '...' : c.description}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Zona de drag & drop */}
      <div
        className={`dropzone ${isDragging ? 'active' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {/* Ícono de la zona de drop */}
        <div className="dropzone-icon">
          {processing ? '⏳' : '📂'}
        </div>
        {/* Título y subtítulo del dropzone */}
        <div className="dropzone-title">
          {processing ? 'Procesando archivos...' : 'Arrastra archivos o carpetas aquí'}
        </div>
        <div className="dropzone-subtitle">
          .eml, .pdf, .docx, .xlsx, .xls, .xlsm, .csv, .png, .jpg, .jpeg, .gif, .webp, .zip, .rar, .7zip, .txt
        </div>
        {/* Botón de selección de carpeta dentro del dropzone */}
        <div style={{ marginTop: '16px' }} onClick={(e) => e.stopPropagation()}>
          <button
            className="btn btn-primary"
            onClick={() => folderInputRef.current?.click()}
            disabled={processing}
          >
            📁 Seleccionar Carpeta
          </button>
        </div>
      </div>

      {/* Input de carpetas oculto */}
      <input
        ref={folderInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileSelect}
        {...{ webkitdirectory: '', directory: '' }}
      />

      {/* Advertencia si hay más de 20 archivos */}
      {files.length > 20 && (
        <div className="file-warning">
          ⚠ Se han cargado más de 20 archivos. El análisis podría tomar más tiempo del esperado.
        </div>
      )}

      {/* Lista de archivos cargados */}
      {files.length > 0 && (
        <div className="file-list">
          {/* Encabezado de la lista con contador */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>
              {files.length} archivo(s) cargado(s)
            </span>
            {/* Botón para limpiar todos los archivos */}
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setFiles([]); showToast('Todos los archivos eliminados', 'info'); }}
            >
              Limpiar todo
            </button>
          </div>
          {/* Renderizar cada archivo */}
          {files.map((item, index) => (
            <div key={index} className="file-item">
              {/* Ícono del tipo de archivo */}
              <span className="file-item-icon">{getFileIcon(item.file.name)}</span>
              {/* Información del archivo */}
              <div className="file-item-info">
                <div className="file-item-name">{item.file.name}</div>
                <div className="file-item-meta">
                  {formatFileSize(item.file.size)} — Origen: {item.origin}
                </div>
              </div>
              {/* Botón para eliminar el archivo */}
              <button className="file-item-remove" onClick={() => removeFile(index)}>
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Botón para iniciar el análisis */}
      {files.length > 0 && (
        <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn btn-primary btn-lg"
            onClick={handleAnalyze}
            disabled={processing}
          >
            🔍 Analizar Solicitud
          </button>
        </div>
      )}
    </div>
  );
}
