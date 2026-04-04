/* ============================================= */
/* MODAL DE CONFIRMACIÓN REUTILIZABLE            */
/* Reemplaza window.confirm() en toda la app     */
/* Usa las mismas clases CSS del modal estándar  */
/* ============================================= */

/**
 * Props:
 *   isOpen      {boolean}   — si el modal está visible
 *   title       {string}    — título del modal
 *   message     {string}    — mensaje / pregunta de confirmación
 *   confirmLabel {string}   — texto del botón de confirmar (default: "Eliminar")
 *   isDanger    {boolean}   — si true, el botón de confirmar usa color de error
 *   onConfirm   {function}  — callback al confirmar
 *   onCancel    {function}  — callback al cancelar o cerrar
 */
export default function ConfirmModal({
  isOpen,
  title = 'Confirmar acción',
  message = '¿Estás seguro? Esta acción no se puede deshacer.',
  confirmLabel = 'Confirmar',
  isDanger = true,
  onConfirm,
  onCancel,
}) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className="modal-content"
        style={{ maxWidth: '420px' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onCancel}>✕</button>
        </div>

        {/* Cuerpo */}
        <div className="modal-body">
          <p style={{ margin: 0, lineHeight: '1.6', color: 'var(--color-text)' }}>
            {message}
          </p>
        </div>

        {/* Footer con botones */}
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            style={isDanger ? { background: 'var(--color-error)', borderColor: 'var(--color-error)' } : {}}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
