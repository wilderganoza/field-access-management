/* ============================================= */
/* PÁGINA DE GESTIÓN DE CASOS                    */
/* CRUD completo para casos de validación        */
/* con modal de creación/edición                 */
/* ============================================= */
import { useState } from 'react';
import { useApp } from '../context/AppContext';
import ConfirmModal from '../components/ConfirmModal';

/* Paleta de 10 colores predefinidos para los casos */
const COLOR_PALETTE = [
  '#3B9EFF', '#F5C842', '#B07EFF', '#22C55E', '#EF4444',
  '#F97316', '#EC4899', '#06B6D4', '#84CC16', '#8B5CF6',
];

/* Emojis sugeridos para los íconos de casos */
const EMOJI_SUGGESTIONS = ['👤', '🚗', '🚙', '🏗️', '📋', '🔧', '⛑️', '🛡️', '📦', '🏭'];

export default function CasesPage() {
  /* Obtener casos y funciones del contexto */
  const { cases, addCase, updateCase, deleteCase, showToast } = useApp();
  /* Estado del modal de creación/edición */
  const [modalOpen, setModalOpen] = useState(false);
  /* Estado del modal de confirmación de eliminación */
  const [confirmModal, setConfirmModal] = useState({ open: false, caseItem: null });
  /* Caso en edición (null = crear nuevo) */
  const [editingCase, setEditingCase] = useState(null);
  /* Estado del formulario del modal */
  const [form, setForm] = useState({
    icon: '📋',
    name: '',
    description: '',
    color: COLOR_PALETTE[0],
    checklist: [''],
  });

  /* Abrir modal para crear un nuevo caso */
  const openCreate = () => {
    /* Resetear el formulario */
    setEditingCase(null);
    setForm({ icon: '📋', name: '', description: '', color: COLOR_PALETTE[0], checklist: [''] });
    setModalOpen(true);
  };

  /* Abrir modal para editar un caso existente */
  const openEdit = (caseItem) => {
    /* Cargar los datos del caso en el formulario */
    setEditingCase(caseItem);
    setForm({
      icon: caseItem.icon,
      name: caseItem.name,
      description: caseItem.description,
      color: caseItem.color,
      checklist: [...caseItem.checklist],
    });
    setModalOpen(true);
  };

  /* Guardar el caso (crear o actualizar) */
  const handleSave = async () => {
    /* Validar campos obligatorios */
    if (!form.name.trim()) {
      showToast('El nombre del caso es obligatorio', 'warning');
      return;
    }
    /* Filtrar preguntas vacías del checklist */
    const cleanChecklist = form.checklist.filter(q => q.trim());
    if (cleanChecklist.length === 0) {
      showToast('Agrega al menos una pregunta al checklist', 'warning');
      return;
    }
    /* Preparar los datos del caso */
    const caseData = { ...form, checklist: cleanChecklist };
    if (editingCase) {
      /* Actualizar caso existente en el backend */
      await updateCase(editingCase.id, caseData);
      showToast('Caso actualizado correctamente', 'success');
    } else {
      /* Crear nuevo caso en el backend */
      await addCase(caseData);
      showToast('Caso creado correctamente', 'success');
    }
    /* Cerrar el modal */
    setModalOpen(false);
  };

  /* Abrir modal de confirmación para eliminar un caso */
  const handleDelete = (caseItem) => {
    setConfirmModal({ open: true, caseItem });
  };

  /* Ejecutar eliminación tras confirmar */
  const handleConfirmDelete = async () => {
    const caseItem = confirmModal.caseItem;
    setConfirmModal({ open: false, caseItem: null });
    await deleteCase(caseItem.id);
    showToast('Caso eliminado', 'info');
  };

  /* Agregar una nueva pregunta vacía al checklist */
  const addChecklistItem = () => {
    setForm(prev => ({ ...prev, checklist: [...prev.checklist, ''] }));
  };

  /* Actualizar el texto de una pregunta del checklist */
  const updateChecklistItem = (index, value) => {
    setForm(prev => {
      const updated = [...prev.checklist];
      updated[index] = value;
      return { ...prev, checklist: updated };
    });
  };

  /* Eliminar una pregunta del checklist */
  const removeChecklistItem = (index) => {
    setForm(prev => ({
      ...prev,
      checklist: prev.checklist.filter((_, i) => i !== index),
    }));
  };

  return (
    <div>
      {/* Encabezado con título y botón de crear */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2>Gestión de Casos</h2>
          <p>Configura los tipos de validación documental disponibles</p>
        </div>
        {/* Botón para crear nuevo caso */}
        <button className="btn btn-primary" onClick={openCreate}>
          + Nuevo Caso
        </button>
      </div>

      {/* Grilla de tarjetas de casos */}
      <div className="case-grid">
        {cases.map(caseItem => (
          <div key={caseItem.id} className="case-card">
            {/* Barra de color superior */}
            <div className="case-card-bar" style={{ background: caseItem.color }} />
            {/* Header con ícono y nombre */}
            <div className="case-card-header">
              <span className="case-card-icon">{caseItem.icon}</span>
              <div>
                <div className="case-card-name">{caseItem.name}</div>
                {/* Badge si es caso por defecto */}
                {caseItem.isDefault && (
                  <span className="case-default-badge">Predeterminado</span>
                )}
              </div>
            </div>
            {/* Descripción del caso */}
            <div className="case-card-desc">{caseItem.description}</div>
            {/* Cantidad de preguntas en el checklist */}
            <div className="case-card-count">
              {caseItem.checklist.length} preguntas en el checklist
            </div>
            {/* Acciones: editar y eliminar */}
            <div className="case-card-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => openEdit(caseItem)}>
                Editar
              </button>
              <button className="btn btn-ghost btn-sm" style={{ color: 'var(--color-error)' }} onClick={() => handleDelete(caseItem)}>
                Eliminar
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Modal de confirmación de eliminación */}
      <ConfirmModal
        isOpen={confirmModal.open}
        title="Eliminar caso"
        message={confirmModal.caseItem ? `¿Eliminar el caso "${confirmModal.caseItem.name}"? Esta acción no se puede deshacer.` : ''}
        confirmLabel="Eliminar"
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmModal({ open: false, caseItem: null })}
      />

      {/* Modal de creación/edición de caso */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          {/* Contenido del modal (detener propagación del clic) */}
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            {/* Header del modal */}
            <div className="modal-header">
              <h3>{editingCase ? 'Editar Caso' : 'Nuevo Caso'}</h3>
              <button className="modal-close" onClick={() => setModalOpen(false)}>✕</button>
            </div>
            {/* Cuerpo del modal con el formulario */}
            <div className="modal-body">
              {/* Campo: Ícono (emoji) */}
              <div className="form-group">
                <label className="form-label">Ícono</label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  {/* Sugerencias de emojis */}
                  {EMOJI_SUGGESTIONS.map(emoji => (
                    <button
                      key={emoji}
                      type="button"
                      style={{
                        fontSize: '24px',
                        padding: '4px 8px',
                        border: form.icon === emoji ? '2px solid var(--color-primary)' : '2px solid transparent',
                        borderRadius: 'var(--radius-sm)',
                        background: form.icon === emoji ? 'var(--color-info-bg)' : 'transparent',
                        cursor: 'pointer',
                      }}
                      onClick={() => setForm(prev => ({ ...prev, icon: emoji }))}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
                {/* Input manual de emoji */}
                <input
                  type="text"
                  className="form-input"
                  value={form.icon}
                  onChange={(e) => setForm(prev => ({ ...prev, icon: e.target.value }))}
                  placeholder="Emoji del caso"
                  style={{ width: '80px' }}
                />
              </div>
              {/* Campo: Nombre del caso */}
              <div className="form-group">
                <label className="form-label">Nombre</label>
                <input
                  type="text"
                  className="form-input"
                  value={form.name}
                  onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Nombre del caso"
                />
              </div>
              {/* Campo: Descripción del caso */}
              <div className="form-group">
                <label className="form-label">Descripción</label>
                <textarea
                  className="form-input form-textarea"
                  value={form.description}
                  onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Descripción del caso de validación"
                />
              </div>
              {/* Campo: Selector de color */}
              <div className="form-group">
                <label className="form-label">Color</label>
                <div className="color-picker">
                  {COLOR_PALETTE.map(color => (
                    <div
                      key={color}
                      className={`color-swatch ${form.color === color ? 'selected' : ''}`}
                      style={{ background: color }}
                      onClick={() => setForm(prev => ({ ...prev, color }))}
                    />
                  ))}
                </div>
              </div>
              {/* Campo: Editor de checklist dinámico */}
              <div className="form-group">
                <label className="form-label">Checklist de Validación</label>
                {/* Lista de preguntas con input por cada una */}
                {form.checklist.map((item, index) => (
                  <div key={index} className="checklist-editor-item">
                    <input
                      type="text"
                      className="form-input"
                      value={item}
                      onChange={(e) => updateChecklistItem(index, e.target.value)}
                      placeholder={`Pregunta ${index + 1}`}
                    />
                    {/* Botón para eliminar pregunta (mínimo 1 debe quedar) */}
                    {form.checklist.length > 1 && (
                      <button
                        type="button"
                        className="checklist-editor-remove"
                        onClick={() => removeChecklistItem(index)}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                {/* Botón para agregar nueva pregunta */}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={addChecklistItem}
                  style={{ marginTop: '4px' }}
                >
                  + Agregar pregunta
                </button>
              </div>
            </div>
            {/* Footer del modal con botones de acción */}
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModalOpen(false)}>
                Cancelar
              </button>
              <button className="btn btn-primary" onClick={handleSave}>
                {editingCase ? 'Guardar Cambios' : 'Crear Caso'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
