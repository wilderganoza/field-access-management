/* ============================================= */
/* PAGINA DE EDICION DE PROMPTS POR CASO         */
/* Cada tipo de caso puede tener sus propias     */
/* instrucciones para la IA en cada paso         */
/* ============================================= */
import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { apiGetPromptsForCase, apiUpdateCasePrompt, apiResetCasePrompt, apiGetDefaultPrompts } from '../utils/api';
import ConfirmModal from '../components/ConfirmModal';

export default function PromptsPage() {
  const { cases, showToast, invalidatePromptsCache } = useApp();

  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [promptList, setPromptList] = useState([]);
  const [, setDefaultContents] = useState({});
  const [loading, setLoading] = useState(false);
  const [backendError, setBackendError] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [editContent, setEditContent] = useState({});
  const [saving, setSaving] = useState({});
  const [confirmModal, setConfirmModal] = useState({ open: false, promptId: null });

  useEffect(() => {
    if (cases.length > 0 && !selectedCaseId) {
      setSelectedCaseId(cases[0].id);
    }
  }, [cases, selectedCaseId]);

  useEffect(() => {
    apiGetDefaultPrompts()
      .then((data) => {
        const map = {};
        for (const p of data.prompts) map[p.id] = p.content;
        setDefaultContents(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    loadPromptsForCase(selectedCaseId);
  }, [selectedCaseId]);

  async function loadPromptsForCase(caseId) {
    setLoading(true);
    setBackendError(false);
    setActiveId(null);
    try {
      const data = await apiGetPromptsForCase(caseId);
      setPromptList(data.prompts);
      const initial = {};
      for (const p of data.prompts) initial[p.id] = p.content;
      setEditContent(initial);
    } catch {
      setBackendError(true);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(promptId) {
    setSaving((prev) => ({ ...prev, [promptId]: true }));
    try {
      await apiUpdateCasePrompt(selectedCaseId, promptId, editContent[promptId]);
      showToast('Prompt guardado para este caso', 'success');
      invalidatePromptsCache(selectedCaseId);
      await loadPromptsForCase(selectedCaseId);
    } catch {
      showToast('Error al guardar el prompt', 'error');
    } finally {
      setSaving((prev) => ({ ...prev, [promptId]: false }));
    }
  }

  function handleRestore(promptId) {
    setConfirmModal({ open: true, promptId });
  }

  async function handleConfirmRestore() {
    const promptId = confirmModal.promptId;
    setConfirmModal({ open: false, promptId: null });
    setSaving((prev) => ({ ...prev, [promptId]: true }));
    try {
      await apiResetCasePrompt(selectedCaseId, promptId);
      showToast('Prompt restaurado al valor predeterminado', 'success');
      invalidatePromptsCache(selectedCaseId);
      await loadPromptsForCase(selectedCaseId);
    } catch {
      showToast('Error al restaurar el prompt', 'error');
    } finally {
      setSaving((prev) => ({ ...prev, [promptId]: false }));
    }
  }

  const selectedCase = cases.find((c) => c.id === selectedCaseId);

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: '0 0 6px', fontSize: '22px', fontWeight: 700 }}>
          Prompts de Inteligencia Artificial
        </h2>
        <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: '14px' }}>
          Personaliza las instrucciones de la IA para cada tipo de caso.
          Usa <code style={{ background: 'var(--color-surface-2)', padding: '1px 5px', borderRadius: '4px' }}>{'{{VARIABLE}}'}</code> para insertar valores dinamicos.
        </p>
      </div>

      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: '14px', whiteSpace: 'nowrap' }}>
            Tipo de caso:
          </span>
          {cases.length === 0 ? (
            <span style={{ color: 'var(--color-text-secondary)', fontSize: '14px' }}>
              No hay casos creados. Ve a <strong>Gestion de Casos</strong> para crear uno.
            </span>
          ) : (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {cases.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCaseId(c.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: selectedCaseId === c.id
                      ? `2px solid ${c.color}`
                      : '2px solid var(--color-border)',
                    background: selectedCaseId === c.id
                      ? `${c.color}18`
                      : 'var(--color-surface)',
                    color: selectedCaseId === c.id ? c.color : 'var(--color-text)',
                    fontWeight: selectedCaseId === c.id ? 600 : 400,
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <span>{c.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {backendError && (
        <div style={{
          padding: '16px 20px',
          borderRadius: '10px',
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          marginBottom: '16px',
        }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600, color: 'var(--color-error)' }}>
            No se puede conectar al servidor backend
          </p>
          <p style={{ margin: '0 0 12px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            Ejecuta <code>node server/index.cjs</code> y luego:
          </p>
          <button className="btn btn-primary" onClick={() => loadPromptsForCase(selectedCaseId)} style={{ fontSize: '13px' }}>
            Reintentar
          </button>
        </div>
      )}

      {!selectedCaseId ? (
        <div style={{ textAlign: 'center', padding: '48px', color: 'var(--color-text-secondary)' }}>
          Selecciona un tipo de caso para ver y editar sus prompts.
        </div>
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px' }}>
          <div className="spinner" />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {promptList.map((prompt, idx) => {
            const isActive = activeId === prompt.id;
            const isDirty = editContent[prompt.id] !== prompt.content;

            return (
              <div
                key={prompt.id}
                className="card"
                style={{
                  padding: 0,
                  overflow: 'hidden',
                  border: isActive
                    ? `2px solid ${selectedCase?.color || 'var(--color-primary)'}`
                    : '1px solid var(--color-border)',
                }}
              >
                <button
                  onClick={() => setActiveId(isActive ? null : prompt.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    padding: '14px 20px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    textAlign: 'left',
                    color: 'var(--color-text)',
                  }}
                >
                  <div
                    style={{
                      width: '34px',
                      height: '34px',
                      borderRadius: '50%',
                      flexShrink: 0,
                      background: selectedCase?.color || 'var(--color-primary)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '14px',
                    }}
                  >
                    {idx + 2}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px' }}>
                        Paso {idx + 2}: {prompt.name}
                      </span>
                      {prompt.is_customized && !isDirty && (
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            background: `${selectedCase?.color || '#3B6EFF'}20`,
                            color: selectedCase?.color || 'var(--color-primary)',
                            fontWeight: 600,
                            border: `1px solid ${selectedCase?.color || '#3B6EFF'}40`,
                          }}
                        >
                          Personalizado
                        </span>
                      )}
                      {isDirty && (
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            background: 'rgba(245, 158, 11, 0.12)',
                            color: 'var(--color-warning)',
                            fontWeight: 600,
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                          }}
                        >
                          Sin guardar
                        </span>
                      )}
                      {!prompt.is_customized && !isDirty && (
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            background: 'var(--color-surface-2)',
                            color: 'var(--color-text-secondary)',
                            fontWeight: 500,
                            border: '1px solid var(--color-border)',
                          }}
                        >
                          Default
                        </span>
                      )}
                    </div>
                    <p style={{ margin: '3px 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                      {prompt.description}
                    </p>
                  </div>

                  <span
                    style={{
                      fontSize: '18px',
                      flexShrink: 0,
                      transform: isActive ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.2s',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    ?
                  </span>
                </button>

                {isActive && (
                  <div style={{ borderTop: '1px solid var(--color-border)', padding: '20px' }}>
                    {prompt.variables && prompt.variables.length > 0 && (
                      <div
                        style={{
                          marginBottom: '14px',
                          padding: '10px 14px',
                          background: 'var(--color-surface-2)',
                          borderRadius: '8px',
                          fontSize: '13px',
                        }}
                      >
                        <strong>Variables disponibles: </strong>
                        {prompt.variables.map((v) => (
                          <code
                            key={v}
                            style={{
                              background: 'var(--color-surface)',
                              border: '1px solid var(--color-border)',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              marginLeft: '6px',
                              fontSize: '12px',
                              color: selectedCase?.color || 'var(--color-primary)',
                            }}
                          >
                            {v}
                          </code>
                        ))}
                      </div>
                    )}

                    <textarea
                      value={editContent[prompt.id] || ''}
                      onChange={(e) => setEditContent((prev) => ({ ...prev, [prompt.id]: e.target.value }))}
                      style={{
                        width: '100%',
                        minHeight: '320px',
                        padding: '12px',
                        background: 'var(--color-surface-2)',
                        color: 'var(--color-text)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '8px',
                        fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace',
                        fontSize: '13px',
                        lineHeight: '1.6',
                        resize: 'vertical',
                        boxSizing: 'border-box',
                      }}
                      placeholder="Escribe las instrucciones del prompt aqui..."
                      spellCheck={false}
                    />

                    <div style={{ display: 'flex', gap: '10px', marginTop: '12px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      {prompt.is_customized && (
                        <button
                          className="btn btn-ghost"
                          onClick={() => handleRestore(prompt.id)}
                          disabled={saving[prompt.id]}
                          style={{ color: 'var(--color-error)' }}
                        >
                          Restaurar default
                        </button>
                      )}
                      <button
                        className="btn btn-ghost"
                        onClick={() => setEditContent((prev) => ({ ...prev, [prompt.id]: prompt.content }))}
                        disabled={!isDirty || saving[prompt.id]}
                      >
                        Descartar cambios
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={() => handleSave(prompt.id)}
                        disabled={!isDirty || saving[prompt.id]}
                        style={selectedCase ? { background: selectedCase.color, borderColor: selectedCase.color } : {}}
                      >
                        {saving[prompt.id] ? 'Guardando...' : 'Guardar para este caso'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!backendError && selectedCaseId && !loading && (
        <div
          style={{
            marginTop: '20px',
            padding: '12px 16px',
            background: 'rgba(59, 110, 255, 0.06)',
            border: '1px solid rgba(59, 110, 255, 0.18)',
            borderRadius: '10px',
            fontSize: '13px',
            color: 'var(--color-text-secondary)',
            lineHeight: '1.6',
          }}
        >
          Los cambios guardados se aplican en el siguiente analisis de este tipo de caso.
          Si no hay prompt personalizado, se usa el <strong>prompt predeterminado</strong> del sistema.
          Las variables entre <code style={{ fontSize: '12px' }}>{'{{ }}'}</code> se reemplazan automaticamente.
        </div>
      )}

      <ConfirmModal
        isOpen={confirmModal.open}
        title="Restaurar prompt predeterminado"
        message="¿Restaurar este prompt al valor predeterminado del sistema? Se perdera la personalizacion guardada para este caso."
        confirmLabel="Restaurar"
        onConfirm={handleConfirmRestore}
        onCancel={() => setConfirmModal({ open: false, promptId: null })}
      />
    </div>
  );
}

