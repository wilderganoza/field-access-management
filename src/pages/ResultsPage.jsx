/* ============================================= */
/* PÁGINA DE RESULTADOS                          */
/* Vista completa del veredicto con 3 tabs:      */
/* Resumen, Documentos y Checklist               */
/* Renderiza markdown en el resumen              */
/* ============================================= */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

export default function ResultsPage({ result }) {
  /* Tab activo: 'resumen' | 'documentos' | 'checklist' */
  const [activeTab, setActiveTab] = useState('resumen');

  /* Si no hay resultado, mostrar estado vacío */
  if (!result) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📭</div>
        <h3>Sin resultados</h3>
        <p>Selecciona una solicitud del historial o procesa una nueva.</p>
      </div>
    );
  }

  /* Determinar la clase de estilo según el veredicto */
  const verdictClass = result.verdict === 'APROBADO' ? 'approved'
    : result.verdict === 'RECHAZADO' ? 'rejected' : 'pending';

  /* Determinar el ícono del veredicto */
  const verdictIcon = result.verdict === 'APROBADO' ? '✅'
    : result.verdict === 'RECHAZADO' ? '❌' : '⚠️';

  /* Formatear la fecha del resultado */
  const formattedDate = new Date(result.timestamp).toLocaleString('es-PE', {
    dateStyle: 'long',
    timeStyle: 'short',
  });

  return (
    <div>
      {/* Banner de veredicto principal */}
      <div className={`verdict-banner ${verdictClass}`}>
        {/* Ícono grande del veredicto */}
        <div className="verdict-icon">{verdictIcon}</div>
        {/* Información del veredicto */}
        <div>
          <div className="verdict-title">
            {result.requestName || (result.verdict === 'APROBADO' ? 'Solicitud Aprobada'
              : result.verdict === 'RECHAZADO' ? 'Solicitud Rechazada'
              : 'Solicitud Pendiente')}
          </div>
          <div className="verdict-subtitle">
            {result.caseIcon} {result.caseName} — {formattedDate}
            {result.verdict && (
              <span style={{ marginLeft: '12px', fontWeight: 600 }}>
                — {result.verdict === 'APROBADO' ? '✅ Aprobada' : result.verdict === 'RECHAZADO' ? '❌ Rechazada' : '⚠️ Pendiente'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Navegación por tabs */}
      <div className="tabs">
        {/* Tab: Resumen */}
        <button
          className={`tab ${activeTab === 'resumen' ? 'active' : ''}`}
          onClick={() => setActiveTab('resumen')}
        >
          Resumen
        </button>
        {/* Tab: Documentos */}
        <button
          className={`tab ${activeTab === 'documentos' ? 'active' : ''}`}
          onClick={() => setActiveTab('documentos')}
        >
          Documentos ({result.files.length})
        </button>
        {/* Tab: Checklist */}
        <button
          className={`tab ${activeTab === 'checklist' ? 'active' : ''}`}
          onClick={() => setActiveTab('checklist')}
        >
          Checklist {Array.isArray(result.checklistResults) && result.checklistResults[0]?.nombre
            ? `(${result.checklistResults.length} personas)`
            : `(${result.checklistResults?.length || 0})`}
        </button>
      </div>

      {/* =========================================== */}
      {/* TAB: RESUMEN                                */}
      {/* =========================================== */}
      {activeTab === 'resumen' && (
        <div>
          {/* Card con el resumen ejecutivo en Markdown */}
          <div className="card" style={{ marginBottom: '16px' }}>
            <div className="card-body">
              <div className="markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{result.summary}</ReactMarkdown>
              </div>
            </div>
          </div>
          {/* Card con datos del correo */}
          <div className="card">
            <div className="card-body">
              <div className="card-title">Datos del Correo</div>
              {/* Grid de datos del correo */}
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', fontSize: '14px' }}>
                {/* Remitente */}
                <span style={{ fontWeight: 600 }}>De:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {result.emailData.from}
                </span>
                {/* Asunto */}
                <span style={{ fontWeight: 600 }}>Asunto:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {result.emailData.subject}
                </span>
                {/* Fecha */}
                <span style={{ fontWeight: 600 }}>Fecha:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {result.emailData.date}
                </span>
                {/* Caso usado para la clasificación */}
                <span style={{ fontWeight: 600 }}>Caso:</span>
                <span>
                  <span style={{
                    display: 'inline-block',
                    padding: '2px 10px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    background: result.caseColor + '20',
                    color: result.caseColor,
                  }}>
                    {result.caseIcon} {result.caseName}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================== */}
      {/* TAB: DOCUMENTOS                             */}
      {/* =========================================== */}
      {activeTab === 'documentos' && (
        <div>
          {result.files.map((file, index) => (
            <div key={index} className="file-item" style={{ marginBottom: '8px' }}>
              {/* Ícono del tipo de archivo */}
              <span className="file-item-icon">
                {file.type === '.pdf' ? '📄' : file.type === '.png' || file.type === '.jpg' || file.type === '.jpeg' ? '🖼️' : file.type === '.docx' || file.type === '.doc' ? '📝' : file.type === '.xlsx' || file.type === '.xls' ? '📊' : '📎'}
              </span>
              {/* Información del archivo */}
              <div className="file-item-info">
                <div className="file-item-name">{file.name}</div>
                <div className="file-item-meta">Tipo: {file.type}</div>
              </div>
              {/* Estado del procesamiento */}
              <span className={`pill ${file.status === 'leído' ? 'pill-success' : file.status === 'saltado' ? 'pill-warning' : 'pill-error'}`}>
                {file.status === 'leído' ? '✓ Leído' : file.status === 'saltado' ? '⏭ Saltado' : '✕ Error'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* =========================================== */}
      {/* TAB: CHECKLIST                              */}
      {/* =========================================== */}
      {activeTab === 'checklist' && (
        <div>
          {/* Detectar si los resultados vienen por persona o en formato plano */}
          {Array.isArray(result.checklistResults) && result.checklistResults[0]?.nombre ? (
            /* Formato por persona/vehículo */
            result.checklistResults.map((persona, pIndex) => {
              const pApproved = (persona.resultados || []).filter(r => r.resultado === 'APROBADO').length;
              const pTotal = (persona.resultados || []).length;
              const pVerdict = (persona.resultados || []).some(r => r.resultado === 'RECHAZADO') ? 'RECHAZADO'
                : (persona.resultados || []).some(r => r.resultado === 'PENDIENTE') ? 'PENDIENTE' : 'APROBADO';
              const pVerdictClass = pVerdict === 'APROBADO' ? 'pill-success' : pVerdict === 'RECHAZADO' ? 'pill-error' : 'pill-warning';
              return (
                <div key={pIndex} style={{ marginBottom: '24px' }}>
                  {/* Encabezado de la persona/vehículo */}
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '12px 16px', background: 'var(--color-bg-tertiary)',
                    borderRadius: '8px', marginBottom: '8px',
                  }}>
                    <div>
                      <span style={{ fontWeight: 700, fontSize: '15px' }}>{persona.nombre}</span>
                      <span style={{ marginLeft: '12px', fontSize: '13px', color: 'var(--color-text-muted)' }}>
                        {pApproved}/{pTotal} aprobados
                      </span>
                    </div>
                    <span className={`pill ${pVerdictClass}`}>{pVerdict}</span>
                  </div>
                  {/* Preguntas del checklist para esta persona */}
                  {(persona.resultados || []).map((item, index) => {
                    const itemClass = item.resultado === 'APROBADO' ? 'approved'
                      : item.resultado === 'RECHAZADO' ? 'rejected' : 'pending-item';
                    const pillClass = item.resultado === 'APROBADO' ? 'pill-success'
                      : item.resultado === 'RECHAZADO' ? 'pill-error' : 'pill-warning';
                    return (
                      <div key={index} className={`checklist-item ${itemClass}`}>
                        <div style={{ flex: 1 }}>
                          <div className="checklist-question">{item.pregunta}</div>
                          <div className="checklist-explanation">{item.explicacion}</div>
                        </div>
                        <span className={`pill ${pillClass}`} style={{ flexShrink: 0, alignSelf: 'flex-start' }}>
                          {item.resultado}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            })
          ) : (
            /* Formato plano (compatibilidad con resultados antiguos) */
            (result.checklistResults || []).map((item, index) => {
              const itemClass = item.resultado === 'APROBADO' ? 'approved'
                : item.resultado === 'RECHAZADO' ? 'rejected' : 'pending-item';
              const pillClass = item.resultado === 'APROBADO' ? 'pill-success'
                : item.resultado === 'RECHAZADO' ? 'pill-error' : 'pill-warning';
              return (
                <div key={index} className={`checklist-item ${itemClass}`}>
                  <div style={{ flex: 1 }}>
                    <div className="checklist-question">{item.pregunta}</div>
                    <div className="checklist-explanation">{item.explicacion}</div>
                  </div>
                  <span className={`pill ${pillClass}`} style={{ flexShrink: 0, alignSelf: 'flex-start' }}>
                    {item.resultado}
                  </span>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
